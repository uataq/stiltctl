import os
import signal
import time
from multiprocessing import Process

from stiltctl.utils import SigtermHandler, timeout


def sigterm_iterator():
    sigterm_handler = SigtermHandler()
    count = 0
    while not sigterm_handler.should_exit:
        time.sleep(0.1)
        count += 1
        if count > 30:
            raise Exception("Did not exit on SIGTERM.")


def sleep_10_seconds():
    time.sleep(10)


def test_sigterm_handler():
    proc = Process(target=sigterm_iterator)
    proc.start()
    os.kill(proc.pid, signal.SIGTERM)
    proc.join()
    assert proc.exitcode != 1
