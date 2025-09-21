# -*- coding: utf-8 -*-
""" memory cache """
#
import time
from threading import RLock, Thread
from typing import Any, Dict, Optional
# 3rd party
from setproctitle import setthreadtitle


class Memcache:
    """
    Memcache - in-memory cache for storing data
    """
    name = 'Memcache.Reaper'

    def __init__(self, logger: Any) -> None:
        self.lock = RLock()
        self.logger = logger
        self.cache: Dict[Any, Dict[str, Any]] = {}

    def set_logger(self, logger: Any) -> None:
        """
        set_logger - set logger (for lazy init)
        """
        self.logger = logger

    def get(self, key: Any) -> Any:
        """
        get - get data by key

        :param key:
        :return:
        """
        value = self.get_ex(key)
        return value.get('data') if value else None

    def get_ex(self, key: Any) -> Optional[Dict[str, Any]]:
        """
        get_ex - get data by key with expiration

        :param key:
        :return:
        """
        with self.lock:
            return self.cache.get(key)

    def set(self, key: Any, value: Any, expires: float = 0) -> None:
        """
        set - set data by key

        :param key:
        :param value:
        :param expires:
        :return:
        """
        with self.lock:
            if expires > 0:
                expires = time.time() + expires
            self.cache[key] = {'data': value, 'expires': expires}

    def delete(self, key: Any) -> None:
        """
        delete - delete data by key

        :param key:
        :return:
        """
        with self.lock:
            del self.cache[key]

    def reaper(self) -> None:
        """
        reaper - reaper thread

        :return:
        """
        setthreadtitle(self.name)
        while True:
            time.sleep(0.1)
            for key in list(self.cache):
                cache_entry = self.get_ex(key)
                if cache_entry:
                    expires = cache_entry.get('expires')
                    if expires is not None and 0 < expires < time.time():
                        self.logger.warning(f'Removing key {key}...')
                        self.delete(key)

    def run_noblock(self) -> None:
        """
        run_noblock - run reaper thread

        :return:
        """
        locker = Thread(target=self.reaper, daemon=True, name=self.name)
        locker.start()
