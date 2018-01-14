from memcache import Client
import logging
import retrying

MEMCACHED_ADDRESS = "localhost:11211"
RETRY_COUNT = 5
STORE_POLLING_TIMEOUT = 2000


def is_none(x):
    return x is None


def is_zero(x):
    return x == 0


class StoreError(Exception):
    pass


class Store(object):
    __instance = None

    def __init__(self, attempts=RETRY_COUNT,
                 poll_timeout=STORE_POLLING_TIMEOUT):
        self.client = Client([MEMCACHED_ADDRESS])
        self.attempts = attempts
        self.poll_timeout = poll_timeout

    def __new__(cls, *a, **k):
        if not cls.__instance:
            cls.__instance = super(Store, cls).__new__(cls)
        return cls.__instance

    def _get(self, key):
        @retrying.retry(retry_on_result=is_none,
                        stop_max_attempt_number=self.attempts,
                        wait_fixed=self.poll_timeout)
        def get_with_retry():
            return self.__instance.client.get(key)
        return get_with_retry()

    def _set(self, key, score, timeout):
        @retrying.retry(retry_on_result=is_zero,
                        stop_max_attempt_number=self.attempts,
                        wait_fixed=self.poll_timeout)
        def set_with_retry():
            return self.__instance.client.set(key, score, timeout)
        return set_with_retry()

    def cache_set(self, key, score, timeout):
        try:
            self._set(key, score, timeout)
        except retrying.RetryError as e:
            logging.warn("Couldn't set value to cache: %s.", e.last_attempt)

    def cache_get(self, key):
        try:
            return self._get(key)
        except retrying.RetryError as e:
            logging.warn("Couldn't get value from cache: %s", e.last_attempt)

    def get(self, key):
        try:
            return self._get(key)
        except retrying.RetryError as e:
            msg = "Couldn't get object from the store: %s" % e.last_attempt
            raise StoreError(msg)
