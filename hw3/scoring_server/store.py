from memcache import Client
from functools import wraps
import logging
import time
import os

MEMCACHED_PORT_ENV = 'MEMCACHED_11211_TCP'
DEFAULT_PORT = 11211
RETRY_COUNT = 5
STORE_POLLING_TIMEOUT_SECONDS = 2


def is_not_none(x):
    return x is not None


def is_not_zero(x):
    return x != 0


def retrying(success_condition, attempts, poll_timeout):
    def decorator(f):
        @wraps(f)
        def retry(*args, **kwargs):
            _attempts = attempts
            while _attempts > 1:
                result = None
                try:
                    result = f(*args, **kwargs)
                except Exception as e:
                    logging.debug(
                        'Got exception %s on attempt to invoke method %s '
                        'with args (%s) and kwargs (%d) retrying in %d s',
                        e.message,
                        f.__name__, ', '.join([str(a) for a in args]),
                        ', '.join(['%s:%s' % (k, v) for k, v
                                   in kwargs.items()]), poll_timeout)
                if success_condition(result):
                    return result
                else:
                    logging.debug('Got unexpected result: %s retrying '
                                  'in %d s', str(result), poll_timeout)
                _attempts -= 1
                time.sleep(poll_timeout)
            return f(*args, **kwargs)
        return retry
    return decorator


class StoreError(Exception):
    pass


class Store(object):

    def __init__(self, attempts=RETRY_COUNT,
                 poll_timeout=STORE_POLLING_TIMEOUT_SECONDS):
        memcached_port = os.environ.get(MEMCACHED_PORT_ENV, DEFAULT_PORT)
        self.client = Client(['localhost:%d' % int(memcached_port)])
        self.attempts = attempts
        self.poll_timeout = poll_timeout

    def _get(self, key):
        @retrying(is_not_none, self.attempts, self.poll_timeout)
        def get_with_retry():
            return self.client.get(key)
        return get_with_retry()

    def _set(self, key, score, timeout):
        @retrying(is_not_zero, self.attempts, self.poll_timeout)
        def set_with_retry():
            return self.client.set(key, score, timeout)
        return set_with_retry()

    def cache_set(self, key, score, timeout):
        try:
            self._set(key, score, timeout)
        except Exception:
            logging.exception("Couldn't set value to cache.")

    def cache_get(self, key):
        try:
            return self._get(key)
        except Exception:
            logging.exception("Couldn't retrieve value from cache.")

    def get(self, key):
        result = None
        try:
            result = self._get(key)
        except Exception as e:
            logging.exception(e)
        if not result:
            raise StoreError("Couldn't retrieve object from store.")
        return result
