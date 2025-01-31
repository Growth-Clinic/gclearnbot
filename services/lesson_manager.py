from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from typing import Optional, Dict, Any
from services.lesson_loader import load_lessons
from services.database import TaskManager, UserManager
import logging


logger = logging.getLogger(__name__)
lessons = load_lessons()


class LessonService:
    def __init__(self, lessons: Dict[str, Any], task_manager: TaskManager, user_manager: UserManager):
        self.lessons = lessons
        self.task_manager = task_manager
        self.user_manager = user_manager

    async def _send_error_message(self, chat_id: int, message: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {message}. Please try /start to restart."
        )

    async def send_lesson(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_key: str) -> None:
        """Send lesson content with progress info and tasks"""
        try:
            chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
            
            # Update progress
            self.user_manager.update_user_progress(chat_id, lesson_key)
            
            lesson = self.lessons.get(lesson_key)
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
                
                # Add available tasks
                available_tasks = self.task_manager.get_tasks_for_lesson(lesson_key)
                if available_tasks:
                    message += "\n\n<b>🌟 Real World Tasks Available!</b>\n"
                    for task in available_tasks:
                        message += f"\n🏢 From <b>{task['company']}</b>:\n"
                        message += f"📝 {task['description']}\n"
                        if task.get("requirements"):
                            message += "<b>Requirements:</b>\n"
                            for req in task["requirements"]:
                                message += f"- {req}\n"
                
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
