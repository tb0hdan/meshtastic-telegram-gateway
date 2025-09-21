# -*- coding: utf-8 -*-
""" Test module for thread manager restart functionality """

import logging
import time
import threading
from threading import Thread
from typing import Any

from .thread_manager import ThreadManager


class MockRunner:
    """Mock runner for testing thread restart functionality"""

    def __init__(self, name: str, should_crash: bool = False, crash_after: float = 2.0):
        self.name = name
        self.exit = False
        self.should_crash = should_crash
        self.crash_after = crash_after
        self.run_count = 0
        self.thread: Any = None

    def run(self) -> None:
        """Mock run method that starts a daemon thread"""
        self.run_count += 1

        if self.should_crash and self.run_count == 1:
            # First run will crash after specified time
            self.thread = Thread(target=self._crash_loop, daemon=True, name=self.name)
        else:
            # Subsequent runs or non-crashing runs
            self.thread = Thread(target=self._normal_loop, daemon=True, name=self.name)

        self.thread.start()

    def _crash_loop(self) -> None:
        """Thread loop that crashes after specified time"""
        time.sleep(self.crash_after)
        # Simulate crash by exiting without setting exit flag
        return

    def _normal_loop(self) -> None:
        """Normal thread loop that runs until exit is set"""
        while not self.exit:
            time.sleep(0.1)

    def shutdown(self) -> None:
        """Shutdown the mock runner"""
        self.exit = True


def test_basic_startup():
    """Test basic thread manager startup"""
    logger = logging.getLogger('test')
    manager = ThreadManager(logger)

    # Create mock runners
    runner1 = MockRunner("TestRunner1")
    runner2 = MockRunner("TestRunner2")

    # Register runners with thread patterns
    manager.register_runner("Test1", runner1, thread_patterns=["TestRunner1"])
    manager.register_runner("Test2", runner2, thread_patterns=["TestRunner2"])

    # Start all
    manager.start_all()

    # Give time for threads to start
    time.sleep(1)

    # Check that threads are running
    thread_names = {t.name for t in threading.enumerate()}
    assert "TestRunner1" in thread_names, "TestRunner1 thread not found"
    assert "TestRunner2" in thread_names, "TestRunner2 thread not found"

    # Shutdown
    manager.shutdown_all()

    print("✓ Basic startup test passed")


def test_restart_functionality():
    """Test thread restart functionality"""
    logger = logging.getLogger('test')
    manager = ThreadManager(logger)

    # Create mock runner that will crash
    runner = MockRunner("CrashingRunner", should_crash=True, crash_after=1.0)

    # Register with short restart delay for testing
    manager.register_runner("Crashing", runner, restart_delay=2.0, thread_patterns=["CrashingRunner"])

    # Start the runner
    manager.start_all()

    # Wait for initial crash and restart
    print("Waiting for crash and restart...")
    time.sleep(8)  # Wait longer for the restart cycle

    # Check that runner was restarted
    assert runner.run_count >= 2, f"Runner should have been restarted, run_count: {runner.run_count}"

    # Check that thread is still running after restart
    thread_names = {t.name for t in threading.enumerate()}
    assert "CrashingRunner" in thread_names, "CrashingRunner thread not found after restart"

    # Shutdown
    manager.shutdown_all()

    print("✓ Restart functionality test passed")


def test_shutdown_prevents_restart():
    """Test that shutdown prevents restarts"""
    logger = logging.getLogger('test')
    manager = ThreadManager(logger)

    # Create mock runner
    runner = MockRunner("ShutdownRunner")
    manager.register_runner("Shutdown", runner)

    # Start and immediately shutdown
    manager.start_all()
    time.sleep(0.5)
    manager.shutdown_all()

    # Wait to ensure no restart attempts
    time.sleep(3)

    # Should only have run once
    assert runner.run_count == 1, f"Runner should have run only once, got: {runner.run_count}"

    print("✓ Shutdown prevents restart test passed")


def test_thread_pattern_functionality():
    """Test that thread patterns work correctly for health monitoring"""
    logger = logging.getLogger('test')
    manager = ThreadManager(logger)

    # Create mock runner with specific thread patterns
    runner = MockRunner("PatternTestRunner")
    manager.register_runner("PatternTest", runner, thread_patterns=["PatternTestRunner"])

    # Start the runner
    manager.start_all()
    time.sleep(1)

    # Verify the runner was registered with correct patterns
    managed_runner = manager.runners["PatternTest"]
    assert managed_runner.thread_patterns == ["PatternTestRunner"], "Thread patterns not correctly registered"

    # Check that the expected thread is running
    thread_names = {t.name for t in threading.enumerate()}
    assert "PatternTestRunner" in thread_names, "PatternTestRunner thread not found"

    # Shutdown
    manager.shutdown_all()

    print("✓ Thread pattern functionality test passed")


def run_all_tests():
    """Run all thread manager tests"""
    print("Running thread manager tests...")

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    try:
        test_basic_startup()
        test_restart_functionality()
        test_shutdown_prevents_restart()
        test_thread_pattern_functionality()
        print("\n✅ All thread manager tests passed!")

    except Exception as exc:
        print(f"\n❌ Test failed: {exc}")
        raise


if __name__ == "__main__":
    run_all_tests()