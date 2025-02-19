from uuid import uuid4
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from services.database import JournalManager, UserManager, FeedbackManager, db, FeedbackAnalyticsManager, AnalyticsManager
from services.feedback_enhanced import evaluate_response_enhanced, analyze_response_quality, format_feedback_message
from services.progress_tracker import ProgressTracker
from services.lesson_manager import LessonService
from services.content_loader import content_loader
from services.feedback_config import LESSON_FEEDBACK_RULES
from services.utils import extract_keywords_from_response
from services.lesson_helpers import get_lesson_structure, is_actual_lesson, get_total_lesson_steps
from services.learning_insights import LearningInsightsManager
import logging
from datetime import datetime, timezone


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__) # Get logger instance

user_data = {} # In-memory storage for user progress

lesson_service = LessonService(user_manager=UserManager())

# Add conversation states
AWAITING_EMAIL = 1

# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

async def cancel_email_collection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel email collection process."""
    await update.message.reply_text(
        "Email collection cancelled. You can use /start anytime to try again."
    )
    return ConversationHandler.END

async def ask_for_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user for email if not provided yet"""
    chat_id = update.message.chat_id
    user_data = await UserManager.get_user_info(chat_id)

    if user_data and "email" in user_data:
        await context.bot.send_message(chat_id, "✅ Your email is already linked!")
    else:
        await context.bot.send_message(chat_id, "📩 Please enter your email to link your account:")
        return

async def save_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the user's email after they provide it"""
    chat_id = update.message.chat_id
    email = update.message.text.strip()

    # Validate email format
    if "@" not in email or "." not in email:
        await context.bot.send_message(chat_id, "❌ Invalid email format. Please enter a valid email:")
        return

    # Check if email is already linked to another user
    existing_user = await UserManager.get_user_by_email(email)
    if existing_user and existing_user["chat_id"] != chat_id:
        await context.bot.send_message(chat_id, "❌ This email is already linked to another account. Please use a different one.")
        return

    # Save email to user profile
    await UserManager.update_user_info(chat_id, {"email": email})
    await context.bot.send_message(chat_id, f"✅ Your email {email} has been linked successfully!")

async def initialize_new_user(user_id: str, email: str = None, platform: str = 'telegram', user_data: dict = None) -> dict:
    """Initialize a new user with standard defaults."""
    base_data = {
        "user_id": user_id,
        "email": email,
        "platform": platform,
        "platforms": [platform],
        "username": user_data.get('username') if user_data else None,
        "first_name": user_data.get('first_name', '') if user_data else '',
        "last_name": user_data.get('last_name', '') if user_data else '',
        "language_code": user_data.get('language_code', 'en') if user_data else 'en',
        "joined_date": datetime.now(timezone.utc).isoformat(),
        "current_lesson": "lesson_1",
        "completed_lessons": [],
        "last_active": datetime.now(timezone.utc).isoformat(),
        "learning_preferences": {
            "preferred_language": user_data.get('language_code', 'en') if user_data else 'en',
            "notification_enabled": True
        },
        "progress_metrics": {
            "total_responses": 0,
            "average_response_length": 0,
            "completion_rate": 0,
            "last_lesson_date": None
        }
    }
    
    # For web platform, add any web-specific fields
    if platform == 'web':
        base_data["username"] = email.split('@')[0]
    
    return base_data

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler with email collection"""
    user = update.message.from_user
    
    # Check if user already exists
    existing_user = await UserManager.get_user_by_telegram_id(user.id)
    
    if existing_user and existing_user.get('email'):
        # User already has email, proceed normally
        welcome_text = """
Welcome back to Growth Clinic! 🌱

Ready to continue your learning journey? Choose your path:
        """
        await show_lesson_menu(update, context)
        return ConversationHandler.END
    else:
        # Ask for email
        await update.message.reply_text(
            "Welcome to Growth Clinic! 🌱\n\n"
            "To get started and sync your progress across platforms, "
            "please share your email address.\n\n"
            "Your email will only be used for account synchronization.",
            reply_markup=ForceReply(selective=True, input_field_placeholder="Enter your email")
        )
        return AWAITING_EMAIL
    
async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle email submission from user with improved error handling and clear feedback."""
    email = update.message.text.strip().lower()
    user = update.message.from_user
    
    if not re.match(EMAIL_REGEX, email):
        await update.message.reply_text(
            "Please provide a valid email address.",
            reply_markup=ForceReply(selective=True)
        )
        return AWAITING_EMAIL
    
    try:
        existing_user = await UserManager.get_user_by_email(email)
        
        if existing_user:
            # Link Telegram account to existing user
            await UserManager.link_telegram_account(
                email=email,
                telegram_id=user.id,
                telegram_data={
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code
                }
            )
            logger.info(f"User linked: {user.id} with email {email}")
            await update.message.reply_text(
                f"✅ Your Telegram account has been successfully linked to {email}.\n"
                "Your progress will be synced across platforms.\n\n"
                "Let's begin your learning journey! 🌱"
            )
        else:
            # Create new user with standard defaults
            user_data = await initialize_new_user(
                str(uuid4()),
                email=email,
                platform='telegram',
                user_data=user.__dict__
            )
            
            success = await UserManager.save_user_info(user_data)
            if not success:
                raise Exception("Failed to save user data")
            
            logger.info(f"User info created: {user.id} with email {email}")    
            await update.message.reply_text(
                f"✅ Your account has been created and email {email} saved.\n"
                "Let's begin your learning journey! 🌱"
            )
        
        # Show lesson menu and end conversation
        await show_lesson_menu(update, context)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error handling email submission: {e}")
        await update.message.reply_text(
            "Sorry, there was an error processing your email. Please try again."
        )
        return AWAITING_EMAIL
    
async def show_lesson_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main lesson menu to users"""
    # Get main lessons
    lessons = content_loader.get_full_lessons(platform='telegram')
    
    keyboard = []
    for lesson_id, lesson in lessons.items():
        if (lesson_id != "lesson_1" and 
            not "congratulations" in lesson_id.lower() and 
            lesson.get("type") == "full_lesson"):
            keyboard.append([
                InlineKeyboardButton(
                    f"📚 {lesson.get('description')}",
                    callback_data=lesson_id
                )
            ])
    
    # Use edit_message or send_message depending on context
    if update.message:
        await update.message.reply_text(
            "Welcome to Growth Clinic! 🌱\n\nChoose your learning path:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif update.callback_query:
        await update.callback_query.message.edit_text(
            "Welcome to Growth Clinic! 🌱\n\nChoose your learning path:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_start_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user's choice between lessons and tasks"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "start_tasks":
        # Temporarily disable task processing
        await query.edit_message_text("Tasks are currently disabled.")
        return
        
        # Original code commented out but preserved
        '''
        content_loader.load_content.cache_clear()

        logger.info("Loading all tasks...")
        tasks = content_loader.get_all_tasks()
        logger.info(f"Loaded tasks: {tasks}")

        keyboard = []
        
        if not tasks:
            logger.warning("No tasks found")
            await query.edit_message_text("No tasks available yet. Please try the full lessons instead.")
            return
            
        for task_id, task in tasks.items():
            logger.info(f"Mapping task: {task_id} -> {task.get('title')}")
            keyboard.append([
                InlineKeyboardButton(
                    f"⚡ {task.get('title', task_id)} ({task.get('estimated_time', 'N/A')})",
                    callback_data=f"task_{task_id}"
                )
            ])
        
        await query.edit_message_text(
            "Choose a task to begin:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        '''



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


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send complete progress report on /progress command"""
    try:
        user_id = update.effective_user.id  # Get user ID from update
        progress_message = await ProgressTracker().get_complete_progress(user_id)
        
        await update.message.reply_text(
            progress_message["text"] if isinstance(progress_message, dict) else progress_message,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in progress command: {e}")
        await update.message.reply_text(
            "Error generating progress report. Please try again later."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🤖 Available commands:

/start - Start or restart the learning journey
/resume - Continue from your last lesson
/journal - View your learning journal entries
/progress - Get a complete progress report
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
    """Send user their learning journal with pagination"""
    # Get chat_id from either message or callback query
    chat_id = update.effective_chat.id  # This works for both message and callback query
    
    # Initialize page number in user data if not exists
    if 'journal_page' not in context.user_data:
        context.user_data['journal_page'] = 0
    
    # Fetch journal from MongoDB
    journal = await db.journals.find_one({"user_id": chat_id})
    
    if journal and journal.get("entries"):
        entries = journal["entries"]
        entries_per_page = 5  # Number of entries per page
        total_pages = (len(entries) + entries_per_page - 1) // entries_per_page
        current_page = context.user_data['journal_page']
        
        # Get entries for current page
        start_idx = current_page * entries_per_page
        end_idx = start_idx + entries_per_page
        page_entries = entries[start_idx:end_idx]
        
        # Format entries for current page
        entries_text = f"📚 Your Learning Journal (Page {current_page + 1}/{total_pages}):\n\n"
        
        for entry in page_entries:
            # Truncate response if too long
            response = entry['response'][:200] + "..." if len(entry['response']) > 200 else entry['response']
            entries_text += f"📝 Lesson: {entry['lesson']}\n"
            entries_text += f"💭 Response: {response}\n"
            entries_text += f"⏰ {entry['timestamp']}\n\n"
        
        # Create navigation buttons
        keyboard = []
        navigation_buttons = []
        
        if current_page > 0:
            navigation_buttons.append(
                InlineKeyboardButton("◀️ Previous", callback_data="journal_prev")
            )
        
        if current_page < total_pages - 1:
            navigation_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data="journal_next")
            )
        
        if navigation_buttons:
            keyboard.append(navigation_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=entries_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending journal page: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Error retrieving journal entries. Please try again."
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="No journal entries found yet. Complete some lessons first!"
        )

# Add this new handler for journal navigation
async def handle_journal_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle journal navigation button clicks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "journal_prev":
        context.user_data['journal_page'] = max(0, context.user_data.get('journal_page', 0) - 1)
    elif query.data == "journal_next":
        context.user_data['journal_page'] = context.user_data.get('journal_page', 0) + 1
    
    # Re-render journal page
    await get_journal(update, context)



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
    """Handle user input and responses with enhanced streak feedback."""
    chat_id = update.message.chat_id
    user_response = update.message.text

    try:
        # Handle feedback collection
        if context.user_data.get('expecting_feedback'):
            success = await FeedbackManager.save_feedback(chat_id, user_response)
            if success:
                await update.message.reply_text("Thank you for your feedback! Our team will review it. 🙏")
            else:
                await update.message.reply_text("Sorry, there was an error saving your feedback. Please try again later.")
            context.user_data['expecting_feedback'] = False
            return

        # Get user's current lesson status
        user_data = await UserManager.get_user_info(chat_id)
        if not user_data or not user_data.get("current_lesson"):
            await update.message.reply_text("Please use /start to begin your learning journey.")
            return

        current_lesson = user_data["current_lesson"]
        lessons = content_loader.load_content('lessons')

        # Handle main lesson to first step transition
        if not '_step_' in current_lesson:
            steps = content_loader.get_lesson_steps(current_lesson)
            if steps:
                current_lesson = list(steps.keys())[0]
                await UserManager.update_user_progress(chat_id, current_lesson)

        # Save journal entry
        save_success = await save_journal_entry(chat_id, current_lesson, user_response)
        if not save_success:
            await update.message.reply_text("There was an error saving your response. Please try again.")
            return

        # Get lesson data
        lesson_data = lessons.get(current_lesson, {})
        next_step = lesson_data.get("next")

        # Generate response feedback
        feedback = evaluate_response_enhanced(current_lesson, user_response, chat_id)
        quality_metrics = analyze_response_quality(user_response)

        quality_metrics = analyze_response_quality(user_response)
        
        # Add learning insights storage
        insights = {
            "emerging_interests": quality_metrics.get('emerging_interests', []),
            "unplanned_skills": quality_metrics.get('skill_analysis', {}).get('skills', []),
            "support_areas": quality_metrics.get('semantic_analysis', {}).get('needs_support', []),
            "learning_trajectory": {
                "velocity": quality_metrics.get('semantic_analysis', {}).get('understanding_velocity', 0),
                "suggested_paths": []  # Will be populated based on analysis
            }
        }
        
        # Store insights
        await LearningInsightsManager.store_learning_insights(chat_id, insights)

        # Get journal entries for streak tracking
        journal = await JournalManager.get_user_journal(chat_id)
        entries = journal.get('entries', []) if journal else []
        
        # Create progress tracker and generate messages
        progress_tracker = ProgressTracker()
        progress_message = progress_tracker.format_progress_message(entries, quality_metrics)
        
        if feedback:
            # Format feedback message with streak information
            feedback_message = await format_feedback_message(feedback, quality_metrics, chat_id)
            
            # Add progress and streak information
            feedback_message += "\n\n" + progress_message
            
            # Send the formatted feedback
            await context.bot.send_message(
                chat_id=chat_id,
                text=feedback_message,
                parse_mode='Markdown'
            )

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
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text(
            "An error occurred. Please try again later."
        )


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