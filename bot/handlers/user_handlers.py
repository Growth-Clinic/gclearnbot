from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.database import JournalManager, UserManager, FeedbackManager, TaskManager, db, FeedbackAnalyticsManager, AnalyticsManager
from services.feedback_enhanced import evaluate_response_enhanced, analyze_response_quality
from services.lesson_manager import LessonService
from services.content_loader import content_loader
from services.feedback_config import LESSON_FEEDBACK_RULES
from services.utils import extract_keywords_from_response
from services.lesson_helpers import get_lesson_structure, is_actual_lesson, get_total_lesson_steps
import logging
from datetime import datetime, timezone
import re


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__) # Get logger instance

user_data = {} # In-memory storage for user progress

lesson_service = LessonService(
    task_manager=TaskManager(),
    user_manager=UserManager()
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler with lesson choices"""
    user = update.message.from_user
    await UserManager.save_user_info(user)
    
    welcome_text = """
Welcome to Growth Clinic! 🌱

Ready to future-proof your career and drive high-growth businesses? Our bite-sized, task-based lessons equip you with essential mental models and skills to thrive in today's fast-paced tech landscape.

🌟 Choose Your Learning Path:

Design Thinking: Solve real-world problems creatively.
Business Modelling: Turn your ideas into sustainable ventures.
Market Thinking: Scale your product to millions.
User Thinking: Understand and engage your audience.
Agile Project Thinking: Execute your ideas efficiently.
Let's get started and transform your skills! 🚀

Need help? Type /help or check the menu beside the text box.
"""
    
    # Load only main lessons (not steps)
    lessons = content_loader.get_full_lessons()
    
    # Create keyboard with lesson choices, filtering out congratulation messages
    keyboard = []
    for lesson_id, lesson in lessons.items():
        # Skip intro lesson, congratulation messages, and ensure it's a full lesson
        if (lesson_id != "lesson_1" and 
            not "congratulations" in lesson_id.lower() and 
            lesson.get("type") == "full_lesson"):
            keyboard.append([
                InlineKeyboardButton(
                    f"📚 {lesson.get('description')}",  # Show action-oriented description
                    callback_data=lesson_id
                )
            ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user's choice between lessons and tasks"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "start_tasks":
        content_loader.load_content.cache_clear()  # Ensure fresh data

        logger.info("Loading all tasks...")
        tasks = content_loader.get_all_tasks()
        logger.info(f"Loaded tasks: {tasks}")

        keyboard = []
        
        if not tasks:
            logger.warning("No tasks found")
            await query.edit_message_text("No tasks available yet. Please try the full lessons instead.")
            return
            
        for task_id, task in tasks.items():
            logger.info(f"Mapping task: {task_id} -> {task.get('title')}")  # ✅ Log task ID
            keyboard.append([
                InlineKeyboardButton(
                    f"⚡ {task.get('title', task_id)} ({task.get('estimated_time', 'N/A')})",
                    callback_data=f"task_{task_id}"  # ✅ Ensure format matches tasks.json
                )
            ])
        
        await query.edit_message_text(
            "Choose a task to begin:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )



async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume from last lesson"""
    try:
        user_id = update.message.from_user.id
        user_data = await UserManager.get_user_info(user_id)
        
        if user_data and user_data.get("current_lesson"):
            await update.message.reply_text("📚 Resuming your last lesson...")
            await lesson_service.send_lesson(update, context, user_data["current_lesson"])
        else:
            await update.message.reply_text("No previous progress found. Use /start to begin!")
    except Exception as e:
        logger.error(f"Error resuming: {e}")
        await update.message.reply_text("Error resuming progress. Please try again.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🤖 Available commands:

/start - Start or restart the learning journey
/resume - Continue from your last lesson
/journal - View your learning journal entries
/help - Show this help message

To progress through lessons:
1. Read the lesson content
2. Complete the given task
3. Send your response
4. Click ✅ when prompted to move forward

Your responses are automatically saved to your learning journal.

    """
    await update.message.reply_text(help_text)


async def get_journal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send the user's learning journal.

    Args:
        update (Update): Incoming update from Telegram.
        context (ContextTypes.DEFAULT_TYPE): Context object containing bot data.

    Returns:
        None
    """
    """Send user their learning journal"""
    chat_id = update.message.chat_id
    
    # Fetch journal from MongoDB
    journal = db.journals.find_one({"user_id": chat_id})
    
    if journal and journal.get("entries"):
        # Format journal entries as text
        entries_text = "📚 Your Learning Journal:\n\n"
        for entry in journal["entries"]:
            entries_text += f"📝 {entry['lesson']}\n"
            entries_text += f"💭 Your response: {entry['response']}\n"
            entries_text += f"⏰ {entry['timestamp']}\n\n"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=entries_text
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="No journal entries found yet. Complete some lessons first!"
        )



async def save_journal_entry(user_id: int, lesson_key: str, response: str) -> bool:
    """
    Save a user's response to their journal and update analytics.
    """
    try:
        # First save the journal entry
        save_success = await JournalManager.save_journal_entry(user_id, lesson_key, response)
        
        if save_success:
            # Update analytics after successful save
            try:
                metrics = await AnalyticsManager.calculate_user_metrics(user_id)
                logger.info(f"Journal entry and analytics updated for user {user_id}")
            except Exception as metrics_error:
                logger.error(f"Error calculating metrics but entry was saved: {metrics_error}")
                # Don't fail the whole operation if just metrics calculation fails
                
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error saving journal entry: {e}", exc_info=True)
        return False


def extract_rating_from_response(response: str) -> str:
    """
    Extract a rating from the user's response.

    Args:
        response (str): The user's feedback response.

    Returns:
        str: The extracted rating (e.g., "5 stars", "4/5"), or "No rating" if none is found.
    """
    # Look for patterns like "5 stars", "4/5", "rating: 3", etc.
    rating_pattern = re.compile(r"(\d+)\s*(stars?|/5|out of 5|rating)", re.IGNORECASE)
    match = rating_pattern.search(response)
    
    if match:
        return f"{match.group(1)} stars"
    return "No rating"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input and responses, including feedback and lesson responses."""
    chat_id = update.message.chat_id
    user_response = update.message.text

    try:
        # Check if the user is sending feedback
        if context.user_data.get('expecting_feedback'):
            # Handle feedback submission
            success = await FeedbackManager.save_feedback(chat_id, user_response)
            if success:
                await update.message.reply_text("Thank you for your feedback! Our team will review it. 🙏")
            else:
                await update.message.reply_text("Sorry, there was an error saving your feedback. Please try again later.")
            context.user_data['expecting_feedback'] = False
            return

        # Get user's current position in the lessons
        user_data = await UserManager.get_user_info(chat_id)
        if not user_data or not user_data.get("current_lesson"):
            await update.message.reply_text("Please use /start to begin your learning journey.")
            return

        current_lesson = user_data["current_lesson"]
        lessons = content_loader.load_content('lessons')

        # If we're on a main lesson, find its first step
        if not '_step_' in current_lesson:
            steps = content_loader.get_lesson_steps(current_lesson)
            if steps:
                current_lesson = list(steps.keys())[0]
                # Update the current lesson to this step
                await UserManager.update_user_progress(chat_id, current_lesson)

        # Save the response to the user's journal
        save_success = await save_journal_entry(chat_id, current_lesson, user_response)
        if not save_success:
            await update.message.reply_text("There was an error saving your response. Please try again.")
            return

        # Get lesson data and next step
        lesson_data = lessons.get(current_lesson, {})
        next_step = lesson_data.get("next")

        # Evaluate response and generate feedback
        feedback = evaluate_response_enhanced(current_lesson, user_response, chat_id)
        quality_metrics = analyze_response_quality(user_response)

        if feedback:
            # Format feedback message
            feedback_message = "📝 Feedback on your response:\n\n"
            feedback_message += "\n\n".join(feedback)

            if quality_metrics['word_count'] < 20:
                feedback_message += "\n\n💡 Tip: Consider expanding your response with more details."
            elif not quality_metrics['has_punctuation']:
                feedback_message += "\n\n💡 Tip: Using proper punctuation can help express your ideas more clearly."

            await update.message.reply_text(feedback_message)

        # Save feedback analytics
        feedback_results = {
            "matches": extract_keywords_from_response(user_response, current_lesson),
            "feedback": feedback,
            "quality_metrics": quality_metrics
        }
        await FeedbackAnalyticsManager.save_feedback_analytics(chat_id, current_lesson, feedback_results)

        # Progress to next step if available
        if next_step:
            logger.info(f"User {chat_id} progressing from {current_lesson} to {next_step}")
            success = await UserManager.update_user_progress(chat_id, next_step)
            if success:
                await lesson_service.send_lesson(update, context, next_step)
            else:
                logger.error(f"Failed to update progress for user {chat_id}")
                await update.message.reply_text("Error updating progress. Please try /resume to continue.")
        else:
            await update.message.reply_text("✅ Response saved! You've completed all lessons.")

    except Exception as e:
        logger.error(f"Error handling message from user {chat_id}: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again later.")



async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button responses."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    user_id = query.message.chat_id

    logger.info(f"User clicked: {callback_data}")

    # Handle lesson selection
    lessons = content_loader.load_content('lessons')
    if callback_data in lessons:
        success = await UserManager.update_user_progress(user_id, callback_data)
        if success:
            await lesson_service.send_lesson(update, context, callback_data)
        else:
            await query.edit_message_text(text="Error progressing. Please try /resume.")
    else:
        await query.edit_message_text(text="Please reply with your input to proceed.")




async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_feedback'):
        chat_id = update.message.chat_id
        user_response = update.message.text
        
        success = await FeedbackManager.save_feedback(chat_id, user_response)
        
        if success:
            await update.message.reply_text(
                "Thank you for your feedback! Our team will review it. 🙏"
            )
        else:
            await update.message.reply_text(
                "Sorry, there was an error saving your feedback. Please try again later."
            )
            
        context.user_data['expecting_feedback'] = False
        return True
    return False