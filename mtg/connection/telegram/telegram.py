# -*- coding: utf-8 -*-
""" Telegram connection module """


import asyncio
import contextlib
import logging
import queue
from typing import Any, Optional

from telegram import Update  # type: ignore[attr-defined]
from telegram.ext import Application


class TelegramConnection:
    """
    Telegram connection
    """

    def __init__(self, token: str, logger: logging.Logger):
        self.logger = logger
        self.msg_queue: Optional[asyncio.Queue] = None
        self.q: queue.Queue = queue.Queue()
        self.queue_task: Optional[asyncio.Task] = None
        self.running = False
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self.application = Application.builder().token(token).build()


    def send_message_sync(self, *args: Any, **kwargs: Any) -> None:
        """
        Send a Telegram message by putting it in the thread-safe queue
        """
        self.q.put((args, kwargs))

    def send_message(self, *args: Any, **kwargs: Any) -> None:
        """
        Send a Telegram message by putting it in the queue

        :param args:
        :param kwargs:
        :return:
        """
        if self.msg_queue is None:
            self.logger.warning("Message queue not initialized yet, message will be dropped")
            return

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Put the message in the queue using thread-safe method
        asyncio.run_coroutine_threadsafe(
            self.msg_queue.put((args, kwargs)),
            loop
        )

    async def _process_message_queue(self) -> None:
        """
        Process messages from the queue asynchronously
        """
        if self.msg_queue is None:
            self.logger.error("Message queue not initialized")
            return

        while self.running:
            try:
                # Get message from the thread-safe queue
                args, kwargs = self.q.get(timeout=1.0)
            except queue.Empty:
                try:
                    args, kwargs = await asyncio.wait_for(self.msg_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
            try:
                # Wait for a message with timeout to allow shutdown
                self.logger.info(args, kwargs)
                try:
                    await self.application.bot.send_message(*args, **kwargs)
                    self.logger.debug(f"Message sent successfully: {kwargs.get('text', 'photo/document')}")
                except (ValueError, TypeError, RuntimeError) as e:
                    if self.logger:
                        self.logger.error(f"Failed to send message: {e}")
            except asyncio.TimeoutError:
                # Timeout is normal, continue checking if we should keep running
                continue
            except (ValueError, TypeError, RuntimeError) as e:
                self.logger.error(f"Error in message queue processor: {e}")

    async def start_queue_processor(self) -> None:
        """
        Start the message queue processor
        """
        if not self.running:
            # Initialize the async queue
            if self.msg_queue is None:
                self.msg_queue = asyncio.Queue()

            self.running = True
            self.queue_task = asyncio.create_task(self._process_message_queue())
            self.logger.info("Message queue processor started")

    async def stop_queue_processor(self) -> None:
        """
        Stop the message queue processor
        """
        self.running = False
        if self.queue_task:
            await self.queue_task
            self.queue_task = None
            self.logger.info("Message queue processor stopped")

    def stop_queue_processor_sync(self) -> None:
        """
        Stop the message queue processor synchronously
        """
        # Signal the queue processor to stop
        self.running = False

        # If there's a queue task, try to handle it properly
        if self.queue_task:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running() and not loop.is_closed():
                    # Cancel the task - this is safe even in a running loop
                    self.queue_task.cancel()
                elif not loop.is_closed():
                    # Loop exists but not running, we can wait for cleanup
                    loop.run_until_complete(self.stop_queue_processor())
            except RuntimeError:
                # No event loop or loop issues, nothing we can do
                pass
            finally:
                self.queue_task = None
                self.logger.info("Message queue processor stopped")

    def poll(self) -> None:
        """
        Run Telegram bot polling

        :return:
        """
        self.logger.info("Polling Telegram...")
        # Start the queue processor before polling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.start_queue_processor())
        self.logger.info("Message queue processor started.")
        # Run polling (this will block)
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def shutdown(self) -> None:
        """
        Stop Telegram bot
        """
        # Stop the queue processor
        self.stop_queue_processor_sync()
        self.application.stop_running()
