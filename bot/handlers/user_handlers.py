from telegram import Update
from telegram.ext import ContextTypes
from services.database import UserManager, FeedbackManager
from services.lesson_manager import LessonService
from config.settings import db
from services.lesson_loader import load_lessons
import logging
from datetime import datetime

logger = logging.getLogger(__name__) # Get logger instance
lessons = load_lessons() # Load lessons from JSON file
user_data = {} # In-memory storage for user progress


lesson_service = LessonService(
    lessons=load_lessons(),
    task_manager=TaskManager(),
    user_manager=UserManager()
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    user = update.message.from_user
    UserManager.save_user_info(user)
    
    welcome_text = """
Welcome to the Learning Bot! 🎓

Available commands:
/start - Start or restart the learning journey
/resume - Continue from your last lesson
/journal - View your learning journal
/feedback - Send feedback or questions to us
/help - Show this help message

Type /start to begin your learning journey!
"""
    await update.message.reply_text(welcome_text)
    await send_lesson(update, context, "lesson_1")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume from last lesson"""
    try:
        user_id = update.message.from_user.id
        user_data = db.users.find_one({"user_id": user_id})
        
        if user_data and user_data.get("current_lesson"):
            await update.message.reply_text("📚 Resuming your last lesson...")
            await send_lesson(update, context, user_data["current_lesson"])
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
/feedback - Send feedback or questions
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



def save_journal_entry(user_id, lesson_key, response):
    """Save a user's response to their journal"""
    # First check if user has an existing journal document
    journal = db.journals.find_one({"user_id": user_id})
    
    if journal:
        # Add new entry to existing journal
        db.journals.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "entries": {
                        "timestamp": datetime.now().isoformat(),
                        "lesson": lesson_key,
                        "response": response
                    }
                }
            }
        )
    else:
        # Create new journal document
        journal = {
            "user_id": user_id,
            "entries": [{
                "timestamp": datetime.now().isoformat(),
                "lesson": lesson_key,
                "response": response
            }]
        }
        db.journals.insert_one(journal)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input and responses"""
    chat_id = update.message.chat_id
    user_response = update.message.text

    # Check if the user is sending feedback
    if context.user_data.get('expecting_feedback'):
        await FeedbackManager.save_feedback(chat_id, user_response)
        await update.message.reply_text("Thank you for your feedback! It has been sent to our team. 🙏")
        context.user_data['expecting_feedback'] = False
        return

    # Default: Process as a lesson response
    current_step = user_data.get(chat_id)
    if current_step in lessons:
        # Save the response to the user's journal
        save_journal_entry(chat_id, current_step, user_response)

        # Get the next step from lessons
        next_step = lessons[current_step].get("next")
        if next_step:
            # Update the user's current step in `user_data`
            user_data[chat_id] = next_step

            # Send confirmation and next lesson
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Response saved! Moving to next step..."
            )
            await send_lesson(update, context, next_step)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Response saved! You've completed all lessons."
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Please use the buttons to navigate lessons."
        )



async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button responses."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press to remove loading state

    next_step = query.data
    if next_step and next_step in lessons:  # Check if next_step exists in lessons
        user_data[query.message.chat_id] = next_step
        await send_lesson(update, context, next_step)
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