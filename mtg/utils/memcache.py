# -*- coding: utf-8 -*-
""" memory cache """
#
import time
from threading import RLock, Thread
#
from setproctitle import setthreadtitle


class Memcache:
    """
    Memcache - in-memory cache for storing data
    """
    name = 'Memcache.Reaper'
    def __init__(self, logger):
        self.lock = RLock()
        self.logger = logger
        self.cache = {}

    def get(self, key):
        """
        get - get data by key
        """
        value = self.get_ex(key)
        return value.get('data') if value else None

    def get_ex(self, key):
        """
        get_ex - get data by key. With expiration meta
        """
        with self.lock:
            value = self.cache.get(key)
            return value


    def set(self, key, value, expires=0):
        """
        set - set data by key. With expiration in seconds
        """
        with self.lock:
            if expires > 0:
                expires = time.time() + expires
            self.cache[key] = {'data': value, 'expires': expires}

    def delete(self, key):
        """
        delete - delete data by key
        """
        with self.lock:
            del self.cache[key]

    def reaper(self):
        """
        reaper - reaper thread for expired keys
        """
        setthreadtitle(self.name)
        while True:
            time.sleep(0.1)
            for key in list(self.cache):
                expires = self.get_ex(key).get('expires')
                if time.time() > expires > 0:
                    self.logger.warning(f'Removing key {key}...')
                    self.delete(key)

    def run_noblock(self):
        """
        run_noblock - non-blocking reaper
        """
        locker = Thread(target=self.reaper, name=self.name)
        locker.setDaemon(True)
        locker.start()
