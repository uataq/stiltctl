import signal
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from loguru import logger


class SigtermHandler:
    def __init__(self):
        """Ensure workload gracefully exits on SIGTERM signal.

        Examples
        --------
        sigterm_handler = SigtermHandler()
        while not sigterm_handler.should_exit:
            print('Still iterating!')
            time.sleep(1)
        """
        self.should_exit = False
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, *args, **kwargs):
        logger.warning("Received SIGTERM. Exiting.")
        self.should_exit = True


def floor_time_to_hour(time: Optional[datetime] = None) -> datetime:
    """Round time down to the nearest hour, defaults to returning current time."""
    if not time:
        time = datetime.utcnow()
    return time.replace(minute=0, second=0, microsecond=0)


@contextmanager
def timeout(seconds: int, raise_timeout_error: bool = False):
    """Context manager to wrap an expression with a timeout handler.

    Args:
        seconds (int): number of seconds to wait before raising TimeoutError.
    Raises:
        TimeoutError: expression did not complete.
    """

    def handle_timeout(*args, **kwargs):
        raise TimeoutError(f"Timeout after {seconds} seconds.")

    default_handler = signal.signal(signal.SIGALRM, handle_timeout)
    signal.alarm(seconds)

    try:
        yield
    except TimeoutError as e:
        if raise_timeout_error:
            raise e
        else:
            logger.exception(e)
    finally:
        signal.signal(signal.SIGALRM, default_handler)
