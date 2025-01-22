import logging
import asyncio
from config.settings import Config
from services.lock_manager import LockManager
from services.application import create_app, start_app, initialize_application
from services.lesson_manager import LessonService
from services.lesson_loader import load_lessons
from services.database import TaskManager, UserManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
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

            # Create event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Initialize the Telegram bot application
                application = loop.run_until_complete(initialize_application())
                
                # Create and start the Quart app
                app = create_app()
                loop.run_until_complete(start_app())
                return 0
            except Exception as e:
                logger.error(f"Application runtime error: {e}")
                return 1
            finally:
                loop.close()
                
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())