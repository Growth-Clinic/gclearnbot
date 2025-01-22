from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.database import UserManager, FeedbackManager, TaskManager, db, FeedbackAnalyticsManager
from services.lesson_manager import LessonService
from services.lesson_loader import load_lessons
import logging
from datetime import datetime, timezone
import re


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__) # Get logger instance


lessons = load_lessons() # Load lessons from JSON file
user_data = {} # In-memory storage for user progress


lesson_service = LessonService(
    lessons=load_lessons(),
    task_manager=TaskManager(),
    user_manager=UserManager()
)


LESSON_FEEDBACK_RULES = {
    "lesson_2": {  # Design Thinking
        "criteria": {
            "Empathy": {
                "keywords": ["feel", "experience", "perspective", "user", "interview", "need", "challenge", "struggle", "pain point"],
                "good_feedback": "✅ Excellent job showing empathy and understanding your user's perspective!",
                "bad_feedback": "⚠️ Try to dig deeper into how your user feels and their experiences."
            },
            "Problem Definition": {
                "keywords": ["problem statement", "needs", "insights", "define", "challenge", "opportunity"],
                "good_feedback": "✅ Clear problem definition that combines user needs and insights!",
                "bad_feedback": "⚠️ Make sure your problem statement includes both user needs and insights."
            },
            "Ideation": {
                "keywords": ["solution", "idea", "creative", "brainstorm", "alternative", "possibility"],
                "good_feedback": "✅ Great variety of creative solutions!",
                "bad_feedback": "⚠️ Try generating more diverse ideas - think outside the box!"
            },
            "Prototyping": {
                "keywords": ["prototype", "test", "mock", "sketch", "wireframe", "design"],
                "good_feedback": "✅ Good job creating a testable prototype!",
                "bad_feedback": "⚠️ Consider making your prototype more concrete and testable."
            }
        }
    },
    "lesson_3": {  # Business Modelling
        "criteria": {
            "Value Proposition": {
                "keywords": ["unique", "offer", "value", "benefit", "solution", "different"],
                "good_feedback": "✅ Strong value proposition that clearly defines your unique offering!",
                "bad_feedback": "⚠️ Make your value proposition more specific and unique."
            },
            "Customer Segments": {
                "keywords": ["segment", "customer", "target", "market", "audience", "demographic"],
                "good_feedback": "✅ Well-defined customer segments with clear characteristics!",
                "bad_feedback": "⚠️ Try to be more specific about who your customers are."
            },
            "Revenue Model": {
                "keywords": ["revenue", "pricing", "monetization", "cost", "profit", "subscription", "freemium"],
                "good_feedback": "✅ Clear and sustainable revenue model!",
                "bad_feedback": "⚠️ Consider different ways to generate revenue."
            },
            "Business Canvas": {
                "keywords": ["canvas", "partnership", "channel", "resource", "activity", "relationship"],
                "good_feedback": "✅ Comprehensive business model canvas with all key elements!",
                "bad_feedback": "⚠️ Make sure to address all nine elements of the business model canvas."
            }
        }
    },
    "lesson_4": {  # Market Thinking
        "criteria": {
            "Product Market Fit": {
                "keywords": ["fit", "need", "solution", "problem", "market", "validation"],
                "good_feedback": "✅ Strong evidence of product-market fit!",
                "bad_feedback": "⚠️ Demonstrate how your product specifically fits market needs."
            },
            "Channel Strategy": {
                "keywords": ["channel", "reach", "marketing", "distribution", "acquisition"],
                "good_feedback": "✅ Well-thought-out channel strategy!",
                "bad_feedback": "⚠️ Consider more specific channels to reach your target market."
            },
            "Growth Metrics": {
                "keywords": ["cac", "ltv", "retention", "conversion", "metrics", "growth"],
                "good_feedback": "✅ Good understanding of key growth metrics!",
                "bad_feedback": "⚠️ Include specific metrics to measure your growth."
            }
        }
    },
    "lesson_5": {  # User Thinking
        "criteria": {
            "Emotional Triggers": {
                "keywords": ["emotion", "feel", "trigger", "motivation", "desire", "need"],
                "good_feedback": "✅ Excellent identification of emotional triggers!",
                "bad_feedback": "⚠️ Dig deeper into the emotional drivers of user behavior."
            },
            "Habit Formation": {
                "keywords": ["habit", "hook", "routine", "behavior", "pattern", "loop"],
                "good_feedback": "✅ Strong understanding of habit-forming mechanics!",
                "bad_feedback": "⚠️ Consider how to make your product more habit-forming."
            },
            "User Psychology": {
                "keywords": ["psychology", "cognitive", "bias", "decision", "behavior"],
                "good_feedback": "✅ Good application of psychological principles!",
                "bad_feedback": "⚠️ Include more psychological insights in your analysis."
            }
        }
    },
    "lesson_6": {  # Project Thinking
        "criteria": {
            "Project Scope": {
                "keywords": ["scope", "goal", "objective", "deliverable", "outcome"],
                "good_feedback": "✅ Clear and well-defined project scope!",
                "bad_feedback": "⚠️ Make your project scope more specific and measurable."
            },
            "Task Management": {
                "keywords": ["task", "milestone", "sprint", "timeline", "priority"],
                "good_feedback": "✅ Well-organized tasks and milestones!",
                "bad_feedback": "⚠️ Break down your tasks into smaller, manageable pieces."
            },
            "Agile Principles": {
                "keywords": ["agile", "iterate", "adapt", "flexible", "review", "retrospective"],
                "good_feedback": "✅ Good application of Agile principles!",
                "bad_feedback": "⚠️ Consider how to make your process more iterative and adaptive."
            }
        }
    }
}


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
    await lesson_service.send_lesson(update, context, "lesson_1")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume from last lesson"""
    try:
        user_id = update.message.from_user.id
        user_data = db.users.find_one({"user_id": user_id})
        
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
    """Save a user's response to their journal."""
    try:
        # First check if user has an existing journal document
        journal = db.journals.find_one({"user_id": user_id})
        
        if journal:
            # Add new entry to existing journal
            db.journals.update_one(
                {"user_id": user_id},
                {
                    "$push": {
                        "entries": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "lesson": lesson_key,
                            "response": response
                        }
                    }
                }
            )
            logger.info(f"Journal entry added for user {user_id} in lesson {lesson_key}")
        else:
            # Create new journal document
            journal = {
                "user_id": user_id,
                "entries": [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "lesson": lesson_key,
                    "response": response
                }]
            }
            db.journals.insert_one(journal)
            logger.info(f"New journal created for user {user_id} with lesson {lesson_key}")
    
    except Exception as e:
        logger.error(f"Error saving journal entry for user {user_id}: {e}", exc_info=True)
        raise


# Helper function to evaluate responses
def evaluate_response(lesson_id: str, response_text: str) -> list:
    """Evaluate the user's response based on predefined rules and provide feedback."""
    try:
        if lesson_id not in LESSON_FEEDBACK_RULES:
            logger.warning(f"No feedback rules found for lesson {lesson_id}")
            return ["No feedback available for this lesson."]
        
        feedback = []
        criteria = LESSON_FEEDBACK_RULES[lesson_id]["criteria"]
        
        for criterion, rules in criteria.items():
            # Find matching keywords
            matches = [kw for kw in rules["keywords"] 
                     if kw.lower() in response_text.lower()]
            
            # Dynamic threshold (30% of keywords needed)
            threshold = len(rules["keywords"]) * 0.3
            feedback.append(
                rules["good_feedback"] if len(matches) >= threshold
                else rules["bad_feedback"]
            )
        
        logger.info(f"Feedback generated for lesson {lesson_id}: {feedback}")
        return feedback
    
    except Exception as e:
        logger.error(f"Error evaluating response for lesson {lesson_id}: {e}", exc_info=True)
        return ["An error occurred while evaluating your response. Please try again."]


def generate_feedback(response_text: str, lesson_key: str) -> str:
    """Generate rule-based feedback for a user's response."""
    feedback = []
    rules = LESSON_FEEDBACK_RULES.get(lesson_key, {})
    
    for criterion, data in rules.get("criteria", {}).items():
        # Check if any keywords exist in the response
        matches = [word for word in data["keywords"] if word in response_text.lower()]
        if matches:
            feedback.append(data["good_feedback"])
        else:
            feedback.append(data["bad_feedback"])
    
    return "\n\n".join(feedback) if feedback else "No feedback available."


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


def extract_keywords_from_response(response: str, lesson_id: str) -> list:
    """
    Extract keywords from the user's response based on the lesson's feedback rules.

    Args:
        response (str): The user's response.
        lesson_id (str): The ID of the current lesson.

    Returns:
        list: A list of keywords found in the response.
    """
    if lesson_id not in LESSON_FEEDBACK_RULES:
        return []
    
    # Get the keywords for the current lesson
    criteria = LESSON_FEEDBACK_RULES[lesson_id]["criteria"]
    keywords = set()
    
    for criterion, rules in criteria.items():
        keywords.update(rules["keywords"])
    
    # Find keywords in the response
    found_keywords = [kw for kw in keywords if kw.lower() in response.lower()]
    return found_keywords


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input and responses, including feedback and lesson responses."""
    chat_id = update.message.chat_id
    user_response = update.message.text

    try:
        # Check if the user is sending feedback
        if context.user_data.get('expecting_feedback'):
            if not user_response.strip():
                await update.message.reply_text("Feedback cannot be empty. Please try again.")
                return

            # Save feedback to the database
            success = await FeedbackManager.save_feedback(chat_id, user_response)
            if success:
                await update.message.reply_text("Thank you for your feedback! It has been sent to our team. 🙏")
                
                # Track feedback rating (if applicable)
                rating = extract_rating_from_response(user_response)
                FeedbackAnalyticsManager.track_feedback_rating(chat_id, rating)
            else:
                await update.message.reply_text("Sorry, there was an error saving your feedback. Please try again later.")
            
            # Reset the feedback expectation flag
            context.user_data['expecting_feedback'] = False
            return

        # Default: Process as a lesson response
        user_data = await UserManager.get_user_info(chat_id)
        if user_data and user_data.get("current_lesson"):
            current_lesson = user_data["current_lesson"]
            
            # Save the response to the user's journal
            save_journal_entry(chat_id, current_lesson, user_response)

            # Evaluate the response and generate feedback
            feedback = evaluate_response(current_lesson, user_response)
            if feedback:
                await update.message.reply_text("📝 Feedback on your response:\n\n" + "\n\n".join(feedback))
                
                # Save feedback analytics
                feedback_results = {
                    "matches": extract_keywords_from_response(user_response, current_lesson),
                    "feedback": feedback
                }
                FeedbackAnalyticsManager.save_feedback_analytics(chat_id, current_lesson, feedback_results)

            # Get the next lesson from the current lesson's "next" field
            next_lesson = lessons.get(current_lesson, {}).get("next")
            if next_lesson:
                # Update the user's current lesson in the database
                await UserManager.update_user_progress(chat_id, next_lesson)
                
                # Send confirmation and the next lesson
                await update.message.reply_text("✅ Response saved! Moving to the next lesson...")
                await lesson_service.send_lesson(update, context, next_lesson)
            else:
                await update.message.reply_text("✅ Response saved! You've completed all lessons.")
        else:
            await update.message.reply_text("Please use /start to begin your learning journey.")
    
    except Exception as e:
        logger.error(f"Error handling message from user {chat_id}: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again later.")



async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button responses."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press to remove loading state

    next_step = query.data
    if next_step and next_step in lessons:  # Check if next_step exists in lessons
        user_data[query.message.chat_id] = next_step
        await lesson_service.send_lesson(update, context, next_step)
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