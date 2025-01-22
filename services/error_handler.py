from telegram import Update
from telegram.ext import CallbackContext
import logging


logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.error(f'Update "{update}" caused error "{context.error}"', exc_info=context.error)
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Sorry, something went wrong. Please try again later or contact support."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}", exc_info=True)