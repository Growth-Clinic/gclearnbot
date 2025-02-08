import logging
import asyncio
from config.settings import Config
from services.lock_manager import LockManager
from services.application import create_app, start_app
from services.lesson_manager import LessonService
from services.content_loader import content_loader
from services.database import TaskManager, UserManager
from services.slack.handlers import start_slack_bot  # Add this import

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

            # Validate content structure before initializing services
            logger.info("Validating content structure...")
            content_loader.validate_content_structure()

            # Initialize services
            try:
                lesson_service = LessonService(
                    task_manager=TaskManager(),
                    user_manager=UserManager()
                )
            except Exception as e:
                logger.error(f"Service initialization failed: {e}")
                return 1

            # Create and start the Quart app
            app = await create_app()
            
            # Start Slack bot if configured
            if Config.SLACK_BOT_TOKEN:
                try:
                    logger.info("Starting Slack bot...")
                    start_slack_bot()
                except Exception as e:
                    logger.error(f"Slack bot initialization failed: {e}")
                    # Continue even if Slack fails - don't stop Telegram bot
            
            await start_app(app)
            return 0
                
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    exit(main())