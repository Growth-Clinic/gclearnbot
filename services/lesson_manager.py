from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from typing import Optional, Dict, Any
from services.content_loader import content_loader
from services.database import TaskManager, UserManager
import logging


logger = logging.getLogger(__name__)
lessons = content_loader.load_content('lessons')


class LessonService:
    def __init__(self, task_manager: TaskManager, user_manager: UserManager):
        """
        Initialize LessonService with dependencies.
        
        Args:
            task_manager: Instance of TaskManager for handling tasks
            user_manager: Instance of UserManager for handling user data
        """
        self.task_manager = task_manager
        self.user_manager = user_manager

    async def _send_error_message(self, chat_id: int, message: str, context: ContextTypes.DEFAULT_TYPE = None) -> None:
        """Send error message to user"""
        if context:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {message}. Please try /start to restart."
            )
        else:
            logger.error(f"Could not send error message to user {chat_id}: {message}")

    async def send_lesson(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_key: str) -> None:
        """Send lesson content with progress info"""
        try:
            chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
            
            # Update progress
            await self.user_manager.update_user_progress(chat_id, lesson_key)
            
            # Get lesson content using content_loader
            lessons = content_loader.load_content('lessons')
            lesson = lessons.get(lesson_key)
            
            if lesson:
                # Format progress header
                parts = lesson_key.split('_')
                lesson_num = parts[1] if len(parts) > 1 else '1'
                step_num = parts[3] if len(parts) > 3 and 'step' in parts else None
                
                # Create progress header
                header = f"<b>📚 Lesson {lesson_num} of 6</b>"
                if step_num:
                    header += f"\n<i>Step {step_num}</i>"
                header += "\n\n"
                
                # Prepare message with header
                message = header + lesson["text"].replace('[', '<').replace(']', '>')
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    disable_web_page_preview=True,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅", callback_data=lesson["next"])]
                    ]) if lesson.get("next") else None
                )
                
        except KeyError as e:
            logger.error(f"Missing lesson key: {e}")
            await self._send_error_message(chat_id, "Lesson not found")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await self._send_error_message(chat_id, "System error", context)

    async def send_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str) -> None:
        """Send task content to user"""
        try:
            chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
            
            # Get task content using content_loader 
            tasks = content_loader.load_content('tasks')
            logger.info(f"Loading task {task_id} from tasks: {tasks}")
            
            # Handle nested structure
            if 'tasks' in tasks:
                tasks = tasks['tasks']
            
            task = tasks.get(task_id)
            
            if task:
                logger.info(f"Found task: {task}")
                message = f"""
    <b>⚡ Quick Task: {task.get('title')}</b>
    ⏱️ Estimated time: {task.get('estimated_time', 'N/A')}

    📝 {task.get('description')}
    """
                if task.get('examples'):
                    message += "\n<b>Examples:</b>\n"
                    for example in task.get('examples', []):
                        message += f"• {example}\n"
                
                # Get related content
                related = content_loader.get_related_content(task_id, 'tasks')
                
                # Add related guides if available
                if related.get('guides'):
                    message += "\n<b>📖 Available Guides:</b>\n"
                    for guide in related['guides']:
                        message += f"• {guide.get('title', 'Guide')}\n"
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Complete Task", callback_data=f"complete_task_{task_id}")]
                    ])
                )
            else:
                logger.error(f"Task {task_id} not found in tasks: {tasks}")
                await self._send_error_message(chat_id, "Task not found", context)
                
        except Exception as e:
            logger.error(f"Error sending task: {e}", exc_info=True)
            await self._send_error_message(chat_id, "Error loading task", context)
