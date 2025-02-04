from quart import Quart
from services.api import setup_routes
from services.database import init_mongodb
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import BotCommand
from bot.handlers.user_handlers import (
    start, resume_command, get_journal, help_command, handle_response, 
    handle_message, handle_start_choice
)
from bot.handlers.admin_handlers import adminhelp_command, list_users, analytics_command, user_analytics_command, lesson_analytics_command
from services.error_handler import error_handler
import logging
import validators
import os
from config.settings import Config

BOT_TOKEN = Config.BOT_TOKEN
WEBHOOK_URL = Config.WEBHOOK_URL
application = None  # Initialize at module level
db = None
logger = logging.getLogger(__name__)


# Set up the bot
async def main() -> Application:
    """
    Initialize and return the bot application.

    This function sets up the bot application by initializing the MongoDB connection,
    creating the bot instance, adding command and message handlers, setting bot commands,
    and configuring the webhook if a webhook URL is provided.

    Returns:
        Application: The initialized bot application.
    """
    global application

    if application is None:
        application = await initialize_application()
    
    return application


async def initialize_application() -> Application:
    try:
        # Initialize database
        # Initialize database connection here if needed
        logger.info("MongoDB connection initialized.")
        logger.info("Using existing MongoDB connection.")

        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is not set.")
        application = Application.builder().token(BOT_TOKEN).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("resume", resume_command))
        application.add_handler(CommandHandler("journal", get_journal))
        application.add_handler(CommandHandler("help", help_command))
        
        # Admin handlers
        application.add_handler(CommandHandler("adminhelp", adminhelp_command))
        application.add_handler(CommandHandler("users", list_users))
        application.add_handler(CommandHandler("analytics", analytics_command))
        application.add_handler(CommandHandler("useranalytics", user_analytics_command))
        application.add_handler(CommandHandler("lessonanalytics", lesson_analytics_command))

        # Message handlers
        application.add_handler(CallbackQueryHandler(handle_start_choice, pattern='^start_'))
        application.add_handler(CallbackQueryHandler(handle_response))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)

        # Initialize the application
        await application.initialize()

        # Set commands
        await application.bot.set_my_commands([
            BotCommand("start", "Start or restart the learning journey"),
            BotCommand("resume", "Continue from your last lesson"),
            BotCommand("journal", "View your learning journal"),
            BotCommand("feedback", "Send feedback"),
            BotCommand("myfeedback", "View your feedback history"),
            BotCommand("help", "Show help information")
        ])
        # Set webhook in application
        if WEBHOOK_URL:
            if validators.url(WEBHOOK_URL):
                webhook_path = f"{WEBHOOK_URL}"
                await application.bot.set_webhook(webhook_path)
                logger.info(f"Webhook set to {webhook_path}")
            else:
                logger.error("Invalid WEBHOOK_URL provided. Webhook not configured.")
        else:
            logger.warning("WEBHOOK_URL environment variable not set. Webhook not configured.")
            logger.warning("WEBHOOK_URL environment variable not set. Webhook not configured.")
        return application
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


async def create_app() -> Quart:
    """Initialize and configure the Quart application"""
    app = Quart(__name__)
    
    # Initialize services
    init_mongodb()
    
    # Initialize the Telegram bot application
    global application
    application = await initialize_application()
    
    # Setup routes
    setup_routes(app, application)  # Pass the application object here
    
    # Setup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.start()
    
    # Add cleanup
    @app.while_serving
    async def lifespan():
        """
        Lifespan function to manage the application's lifecycle.

        This function ensures that the scheduler is properly shut down
        when the application stops serving.
        """
        yield
        scheduler.shutdown()
    
    return app


async def start_app(app):
    """Start the Quart application"""
    port = int(os.getenv('PORT', 8080))
    await app.run_task(host='0.0.0.0', port=port)