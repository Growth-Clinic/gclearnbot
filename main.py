import logging
import asyncio
from config.settings import Config
from services.lock_manager import LockManager
from services.application import create_app, start_app
from services.lesson_manager import LessonService
from services.lesson_loader import load_lessons
from services.database import TaskManager, UserManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def async_main():
    try:
        with LockManager() as lock:
            if not lock.lock_acquired:
                logger.error("Could not acquire lock, exiting")
                return 1

            # Initialize services
            try:
                lesson_service = LessonService(
                    lessons=load_lessons(),
                    task_manager=TaskManager(),
                    user_manager=UserManager()
                )
            except Exception as e:
                logger.error(f"Service initialization failed: {e}")
                return 1

            # Create and start the Quart app
            app = await create_app()
            await start_app()
            return 0
                
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    exit(main())