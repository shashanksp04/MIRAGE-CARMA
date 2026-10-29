"""Nonblocking process lock shared by API and CLI on the same data directory."""
import fcntl
import threading


class BusyError(RuntimeError):
    pass


class RunLock:
    def __init__(self, data_dir):
        self.path = data_dir / "active.lock"
        self._mutex = threading.Lock()
        self._handle = None

    def acquire(self):
        if not self._mutex.acquire(blocking=False):
            raise BusyError("A demo query or runtime reset is already active")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                raise BusyError("A demo query or runtime reset is already active") from None
            self._handle = handle
        except BaseException:
            self._mutex.release()
            raise

    def release(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None
            self._mutex.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
