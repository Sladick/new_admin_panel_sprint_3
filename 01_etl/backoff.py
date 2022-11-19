from functools import wraps
from time import sleep
from elasticsearch.exceptions import ConnectionError
from psycopg2 import OperationalError
import logging


def backoff(start_sleep_time=0.1, factor=2, border_sleep_time=10) -> int:
    """Функция для повторного выполнения функции через некоторое время, если
    возникла ошибка.

    Args:
        start_sleep_time (float, optional): начальное время повтора.
        factor (int, optional): во сколько раз нужно увеличить время ожидания.
        border_sleep_time (int, optional): граничное время ожидания.
    """
    def func_wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            t = start_sleep_time
            while True:
                try:
                    conn = func(*args, **kwargs)
                    break
                except (OperationalError, ConnectionError):
                    logging.exception()
                    if t < border_sleep_time:
                        t = t * 2 ** factor
                    if t > border_sleep_time:
                        t = border_sleep_time
                    sleep(t)
            return conn
        return inner
    return func_wrapper