from pathlib import Path
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LockManager:
    def __init__(self, lockfile_path: str = "/tmp/telegram_bot.lock"):
        self.lockfile = Path(lockfile_path)
        self.lock_acquired = False

    def acquire_lock(self) -> bool:
        """Attempt to acquire the lock file"""
        try:
            if self.lockfile.exists():
                with open(self.lockfile) as f:
                    pid = int(f.read())
                try:
                    os.kill(pid, 0)  # Check if process is running
                    logger.warning(f"Another instance is running (PID: {pid})")
                    return False
                except (OSError, ValueError):
                    # Process doesn't exist, remove stale lock
                    self.lockfile.unlink(missing_ok=True)
            
            # Create new lock
            with open(self.lockfile, 'w') as f:
                f.write(str(os.getpid()))
            self.lock_acquired = True
            logger.info(f"Lock acquired at {self.lockfile}")
            return True
            
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return False

    def release_lock(self) -> None:
        """Release the lock file"""
        try:
            if self.lock_acquired and self.lockfile.exists():
                self.lockfile.unlink()
                logger.info("Lock released")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")

    def __enter__(self):
        if not self.acquire_lock():
            raise RuntimeError("Could not acquire lock")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_lock()

def is_already_running() -> bool:
    """Check if another instance is running"""
    return not LockManager().acquire_lock()