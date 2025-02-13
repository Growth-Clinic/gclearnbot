import logging
import asyncio
from config.settings import Config
from services.lock_manager import LockManager
from services.application import create_app, start_app
from services.lesson_manager import LessonService
from services.content_loader import content_loader
from services.database import TaskManager, UserManager, init_mongodb
from services.slack.handlers import start_slack_bot
from hypercorn.config import Config as HypercornConfig
from hypercorn.asyncio import serve

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

            # Initialize database first
            logger.info("Initializing database connection...")
            db = await init_mongodb()
            if not db:
                logger.error("Failed to initialize database")
                return 1

            # Create Quart app
            logger.info("Initializing web application...")
            app = await create_app()

            # Configure Hypercorn
            hypercorn_config = HypercornConfig()
            hypercorn_config.bind = [f"0.0.0.0:{int(Config.PORT)}"]
            hypercorn_config.worker_class = "asyncio"

            # Start the web server in the background
            server = asyncio.create_task(serve(app, hypercorn_config))
            logger.info(f"Web server starting on port {Config.PORT}")

            # Validate content structure
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

            # Start Telegram bot
            logger.info("Starting Telegram bot...")
            await start_app(app)
            
            # Start Slack bot if configured
            if Config.SLACK_BOT_TOKEN and Config.SLACK_APP_TOKEN:
                try:
                    logger.info("Starting Slack bot...")
                    start_slack_bot()
                    logger.info("Slack bot started successfully")
                except Exception as e:
                    logger.error(f"Slack bot initialization failed: {e}")
                    logger.info("Continuing with Telegram bot only")
            
            # Keep the application running
            await server

            return 0
                
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    exit(main())