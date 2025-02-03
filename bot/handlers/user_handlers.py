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
    """Start command handler with learning path choices"""
    user = update.message.from_user
    await UserManager.save_user_info(user)
    
    welcome_text = """
Welcome to the Learning Bot! 🎓

I can help you learn through:
• Full Lessons: Comprehensive learning paths 📚
• Quick Tasks: Short, focused exercises ⚡

Choose your learning style below:

Available commands:
/start - Start or restart the learning journey
/resume - Continue from your last lesson
/journal - View your learning journal
/feedback - Send feedback or questions to us
/help - Show this help message
"""
    
    # Create keyboard with learning choices
    keyboard = [
        [
            InlineKeyboardButton("📚 Full Lessons", callback_data="start_lessons"),
            InlineKeyboardButton("⚡ Quick Tasks", callback_data="start_tasks")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user's choice between lessons and tasks"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "start_lessons":
        # Get available full lessons
        lessons = content_loader.get_full_lessons()
        keyboard = []
        for lesson_id, lesson in lessons.items():
            # Skip congratulations lessons
            if 'congratulations' not in lesson_id:
                keyboard.append([InlineKeyboardButton(
                    f"📚 {lesson.get('type', 'Lesson')}: {lesson.get('description', '')}",
                    callback_data=lesson_id
                )])
        
        await query.edit_message_text(
            "Choose a lesson to begin:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif choice == "start_tasks":
        # Get available quick tasks
        tasks = content_loader.get_quick_tasks()
        keyboard = []
        for task_id, task in tasks.items():
            # Add better task description
            keyboard.append([InlineKeyboardButton(
                f"⚡ {task.get('title', '')} ({task.get('estimated_time', 'N/A')})",
                callback_data=f"task_{task_id}"
            )])
        
        await query.edit_message_text(
            "Choose a quick task to begin:",
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



async def my_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to let users view their own feedback history"""
    try:
        user_id = update.message.from_user.id
        feedback_list = await FeedbackManager.get_user_feedback(user_id)
        
        if not feedback_list:
            await update.message.reply_text("You haven't submitted any feedback yet.")
            return
            
        report = "📋 Your Feedback History:\n\n"
        for feedback in feedback_list:
            timestamp = feedback['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            report += f"📅 {timestamp}\n"
            report += f"💭 {feedback['feedback']}\n"
            report += "------------------------\n\n"
        
        # Split long reports into multiple messages if needed
        if len(report) > 4096:
            for i in range(0, len(report), 4096):
                await update.message.reply_text(report[i:i+4096])
        else:
            await update.message.reply_text(report)
            
    except Exception as e:
        logger.error(f"Error viewing user feedback: {e}", exc_info=True)
        await update.message.reply_text("Error retrieving your feedback. Please try again later.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🤖 Available commands:

/start - Start or restart the learning journey
/resume - Continue from your last lesson
/journal - View your learning journal 
/feedback - Send feedback
/myfeedback - View your feedback history
/help - Show this help message

To progress through lessons:
1. Read the lesson content
2. Complete the given task
3. Send your response
4. Click ✅ when prompted to move forward

Your responses are automatically saved to your learning journal.
    """
    await update.message.reply_text(help_text)



async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle feedback command"""
    await update.message.reply_text(
        "Please share your feedback or questions. Your message will be sent to our team."
    )
    context.user_data['expecting_feedback'] = True



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

    # Handle task selection
    if callback_data.startswith('task_'):
        task_id = callback_data.replace('task_', '')
        await lesson_service.send_task(update, context, task_id)
        return

    # Handle task completion
    if callback_data.startswith('complete_task_'):
        task_id = callback_data.replace('complete_task_', '')
        await query.edit_message_text(
            text="🎉 Task completed! Use /start to choose another task or lesson.",
            parse_mode='HTML'
        )
        return

    # Handle lesson progression
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