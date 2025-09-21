# -*- coding: utf-8 -*-
""" Thread manager for handling crashed threads with restart functionality """

import logging
import time
import threading
from threading import Thread, Event
from typing import Any, Dict, List, Optional, Set


class ManagedRunner:  # pylint: disable=too-many-instance-attributes
    """
    Wrapper for runner objects that provides restart functionality
    """

    def __init__(self, name: str, runner_obj: Any, logger: logging.Logger, *,  # pylint: disable=too-many-arguments
                 restart_delay: float = 5.0, max_restart_attempts: int = -1,
                 thread_patterns: Optional[List[str]] = None):
        self.name = name
        self.runner_obj = runner_obj
        self.logger = logger
        self.restart_delay = restart_delay
        self.max_restart_attempts = max_restart_attempts
        self.thread_patterns = thread_patterns or []
        self.restart_count = 0
        self.thread: Optional[Thread] = None
        self.shutdown_event = Event()
        self.monitor_thread: Optional[Thread] = None
        self.last_thread_count = 0
        self.thread_names_before: Set[str] = set()
        self.startup_time = time.time()

    def start(self) -> None:
        """Start the managed runner and its monitor"""
        if self.shutdown_event.is_set():
            return

        # Start the runner
        self._start_runner()

        # Start the monitor thread
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_thread = Thread(
                target=self._monitor_loop,
                daemon=True,
                name=f"{self.name}-Monitor"
            )
            self.monitor_thread.start()

    def _start_runner(self) -> None:
        """Start the actual runner thread"""
        if self.thread is not None and self.thread.is_alive():
            return

        self.logger.info(f"Starting {self.name}")

        # Capture thread names before starting
        self.thread_names_before = {t.name for t in threading.enumerate()}

        # Call the original run method which should start daemon threads
        try:
            self.runner_obj.run()
            self.logger.debug(f"{self.name} run() method completed")

            # Give threads a moment to start
            time.sleep(0.5)

            # Capture new thread names to monitor
            thread_names_after = {t.name for t in threading.enumerate()}
            new_threads = thread_names_after - self.thread_names_before

            if new_threads:
                self.logger.debug(f"{self.name} started threads: {new_threads}")

            self.startup_time = time.time()

        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.error(f"Error starting {self.name}: {exc}")

    def _monitor_loop(self) -> None:
        """Monitor the runner and restart if needed"""
        while not self.shutdown_event.is_set():
            time.sleep(1)  # Check every second

            if self.shutdown_event.is_set():
                break

            # Check if we need to restart
            if self._should_restart():
                if self.max_restart_attempts >= 0 and self.restart_count >= self.max_restart_attempts:
                    self.logger.error(f"{self.name} exceeded max restart attempts ({self.max_restart_attempts})")
                    break

                self.logger.warning(f"{self.name} needs restart (attempt {self.restart_count + 1})")
                self._perform_restart()

    def _should_restart(self) -> bool:
        """Check if the runner needs to be restarted"""
        # Don't restart if shutting down
        if hasattr(self.runner_obj, 'exit') and self.runner_obj.exit:
            return False

        # Don't restart too soon after startup (give time to initialize)
        if time.time() - self.startup_time < 3:
            return False

        # Check for runner-specific health indicators
        return self._check_runner_health()

    def _check_runner_health(self) -> bool:
        """Check runner-specific health indicators"""
        current_threads = {t.name for t in threading.enumerate() if t.is_alive()}

        # Runner-specific thread name patterns to check
        expected_patterns = self._get_expected_thread_patterns()

        for pattern in expected_patterns:
            if not any(pattern in thread_name for thread_name in current_threads):
                self.logger.warning(f"{self.name}: Expected thread with pattern '{pattern}' not found")
                return True  # Need restart

        return False  # All expected threads found

    def _get_expected_thread_patterns(self) -> List[str]:
        """Get expected thread name patterns for this runner"""
        return self.thread_patterns

    def _perform_restart(self) -> None:
        """Perform the actual restart"""
        self.restart_count += 1

        # Wait for restart delay
        if not self.shutdown_event.wait(self.restart_delay):
            self.logger.info(f"Restarting {self.name}")
            self._start_runner()

    def shutdown(self) -> None:
        """Shutdown the managed runner"""
        self.logger.info(f"Shutting down {self.name}")
        self.shutdown_event.set()

        # Call the runner's shutdown method if it exists
        if hasattr(self.runner_obj, 'shutdown'):
            try:
                self.runner_obj.shutdown()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.logger.error(f"Error shutting down {self.name}: {exc}")


class ThreadManager:
    """
    Thread manager for handling multiple runners with restart functionality
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.runners: Dict[str, ManagedRunner] = {}
        self.shutdown_event = Event()

    def register_runner(self, name: str, runner_obj: Any, *,  # pylint: disable=too-many-arguments
                       restart_delay: float = 5.0, max_restart_attempts: int = -1,
                       thread_patterns: Optional[List[str]] = None) -> None:
        """Register a runner for management"""
        if name in self.runners:
            self.logger.warning(f"Runner {name} already registered, replacing")

        self.runners[name] = ManagedRunner(
            name=name,
            runner_obj=runner_obj,
            logger=self.logger,
            restart_delay=restart_delay,
            max_restart_attempts=max_restart_attempts,
            thread_patterns=thread_patterns
        )

    def start_all(self) -> None:
        """Start all registered runners"""
        self.logger.info("Starting all managed runners")
        for name, runner in self.runners.items():
            try:
                runner.start()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.logger.error(f"Failed to start {name}: {exc}")

    def shutdown_all(self) -> None:
        """Shutdown all managed runners"""
        self.logger.info("Shutting down all managed runners")
        self.shutdown_event.set()

        for name, runner in self.runners.items():
            try:
                runner.shutdown()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.logger.error(f"Error shutting down {name}: {exc}")

    def get_runner_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all runners"""
        return {
            name: {
                'restart_count': runner.restart_count,
                'max_restart_attempts': runner.max_restart_attempts,
                'shutdown': runner.shutdown_event.is_set()
            }
            for name, runner in self.runners.items()
        }
