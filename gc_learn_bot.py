from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode  
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)
from quart import Quart, request, jsonify, Response
from quart.typing import ResponseReturnValue
import threading
import json
from pathlib import Path
import sys
from pymongo.errors import ServerSelectionTimeoutError, DuplicateKeyError, OperationFailure
import time
import os
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi
import asyncio
from asyncio import run



# Lock file check
def is_already_running():
    lockfile = Path("/tmp/telegram_bot.lock")
    
    if lockfile.exists():
        try:
            with open(lockfile) as f:
                pid = int(f.read())
            os.kill(pid, 0)  # Check if process is running
            return True
        except (OSError, ValueError):
            lockfile.unlink(missing_ok=True)
    
    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))
    return False



# Create Quart app
app = Quart(__name__)
scheduler = AsyncIOScheduler()



# Global application instance
application: Optional[Application] = None



# Load environment variables
load_dotenv()

# Initialize bot with environment variable
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

# Get webhook URL from environment
WEBHOOK_URL = os.getenv('WEBHOOK_URL')



@app.route('/webhook', methods=['POST'])
async def webhook() -> ResponseReturnValue:
    """Handle incoming webhook updates"""
    try:
        if not application:
            logger.error("Application not initialized")
            return jsonify({"status": "error", "message": "Application not initialized"}), 500
            
        if not application.bot:
            logger.error("Bot not initialized")
            return jsonify({"status": "error", "message": "Bot not initialized"}), 500
            
        json_data = await request.get_json(force=True)
        logger.info(f"Received webhook data: {json_data}")  # Log incoming data
        
        update = Update.de_json(json_data, application.bot)
        await application.process_update(update)
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)  # Added exc_info for stack trace
        return jsonify({"status": "error", "message": str(e)}), 500


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create directories for storage
def init_mongodb(max_retries=3, retry_delay=2):
    """Initialize MongoDB connection with retry mechanism"""
    for attempt in range(max_retries):
        try:
            MONGODB_URI = os.getenv('MONGODB_URI')
            if not MONGODB_URI:
                raise ValueError("MONGODB_URI environment variable not set!")

            client = MongoClient(
                MONGODB_URI,
                tlsCAFile=certifi.where(),
                tls=True,
                retryWrites=True,
                serverSelectionTimeoutMS=10000,    # Increased timeout
                connectTimeoutMS=30000,            # Increased timeout
                maxPoolSize=1,                     # Reduced connections
                minPoolSize=1
            )
            
            # Test connection with longer timeout
            client.admin.command('ping', serverSelectionTimeoutMS=10000)
            db = client['telegram_bot']
            # Ensure an index on user_id for journals collection
            db.journals.create_index("user_id")
            
            logger.info("MongoDB connection successful")
            return db
            
        except ServerSelectionTimeoutError as e:
            if attempt == max_retries - 1:
                logger.error(f"MongoDB connection timeout after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s...")
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            raise

# Initialize MongoDB connection
db = init_mongodb()

# Configure admin users
ADMIN_IDS = [
    471827125,  # add other admin Telegram user ID
]

class UserManager:
    @staticmethod
    def update_progress(user_id: int, lesson_key: str) -> None:
        """Update user's lesson progress"""
        try:
            db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "current_lesson": lesson_key,
                        "last_activity": datetime.now(timezone.utc)
                    },
                    "$addToSet": {
                        "completed_lessons": lesson_key
                    }
                },
                upsert=True
            )
            logger.info(f"Progress updated for user {user_id}: {lesson_key}")
        except Exception as e:
            logger.error(f"Error updating progress: {e}")


    @staticmethod
    async def save_user_info(user) -> Dict[str, Any]:
        """
        Save user information when they start using the bot.
        
        Args:
            user: Telegram user object
            
        Returns:
            Dict containing saved user data
            
        Raises:
            OperationFailure: If MongoDB operation fails
        """
        try:
            user_data = {
                "user_id": user.id,
                "username": user.username or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "", 
                "language_code": user.language_code or "en",
                "joined_date": datetime.now(timezone.utc).isoformat(),
                "current_lesson": "lesson_1",
                "completed_lessons": [],
                "last_active": datetime.now(timezone.utc).isoformat()
            }
            
            result = db.users.update_one(
                {"user_id": user.id},
                {
                    "$set": user_data,
                    "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
            
            if not result.acknowledged:
                raise OperationFailure("Failed to save user data")
                
            logger.info(f"User data saved/updated for user {user.id}")
            return user_data
            
        except OperationFailure as e:
            logger.error(f"Database error saving user {user.id}: {e}")
            raise

    @staticmethod
    async def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User data dictionary or None if not found
            
        Raises:
            OperationFailure: If MongoDB query fails
        """
        try:
            user = db.users.find_one({"user_id": user_id})
            if user:
                user.pop('_id', None)  # Remove MongoDB ID
            return user
            
        except OperationFailure as e:
            logger.error(f"Database error fetching user {user_id}: {e}")
            raise

    @staticmethod
    async def update_user_progress(user_id: int, lesson_key: str) -> bool:
        """
        Update user's progress.
        
        Args:
            user_id: Telegram user ID
            lesson_key: Current lesson identifier
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            OperationFailure: If MongoDB update fails
        """
        try:
            if not lesson_key in lessons:
                logger.error(f"Invalid lesson key: {lesson_key}")
                return False
                
            result = db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "current_lesson": lesson_key,
                        "last_active": datetime.now(timezone.utc).isoformat()
                    },
                    "$addToSet": {"completed_lessons": lesson_key}
                }
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Progress updated for user {user_id}: {lesson_key}")
            return success
            
        except OperationFailure as e:
            logger.error(f"Database error updating progress for user {user_id}: {e}")
            raise


class FeedbackManager:
    """Manages feedback operations in MongoDB"""

    @staticmethod
    async def save_feedback(user_id: int, feedback_text: str) -> bool:
        """
        Save user feedback with validation and error handling.

        Args:
            user_id: Telegram user ID
            feedback_text: User's feedback message

        Returns:
            bool: True if save successful, False otherwise
            
        Raises:
            OperationFailure: If MongoDB operation fails
        """
        try:
            # Get the current max ID and increment it
            current_max_id = await asyncio.to_thread(
                lambda: db.feedback.find_one(sort=[("id", -1)]) or {}
            )
            new_id = (current_max_id.get("id", 0) + 1)

            feedback_data = {
                "id": new_id,  # New numeric ID
                "user_id": user_id,
                "feedback": feedback_text.strip(),
                "timestamp": datetime.now(timezone.utc),
                "processed": False
            }
            
            result = await asyncio.to_thread(
                db.feedback.insert_one,
                feedback_data
            )
            
            success = result.acknowledged
            if success:
                logger.info(f"Feedback saved for user {user_id} with ID {new_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error saving feedback: {e}", exc_info=True)
            return False
        
    @staticmethod 
    async def get_user_feedback(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get feedback history for a specific user.
        
        Args:
            user_id: Telegram user ID
            limit: Maximum number of feedback items to return
            
        Returns:
            List of feedback documents
        """
        try:
            # Debug logging
            logger.info(f"Fetching feedback for user {user_id}")
            
            cursor = db.feedback.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit)
            
            feedback_list = []
            for doc in cursor:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                feedback_list.append(doc)
            
            logger.info(f"Found {len(feedback_list)} feedback items for user {user_id}")
            return feedback_list
            
        except Exception as e:
            logger.error(f"Error retrieving user feedback: {e}", exc_info=True)
            return []

    @staticmethod 
    def get_all_feedback(processed: bool = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get feedback with optional filtering and pagination.

        Args:
            processed: Filter by processed status if provided
            limit: Maximum number of feedback items to return
            
        Returns:
            List of feedback documents
            
        Raises:
            OperationFailure: If MongoDB query fails
        """
        try:
            query = {}
            if processed is not None:
                query["processed"] = processed
                
            cursor = db.feedback.find(query).sort("timestamp", -1).limit(limit)
            
            # Convert ObjectId to string and return the list
            feedback_list = []
            for doc in cursor:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])  # Convert ObjectId to string
                feedback_list.append(doc)
                
            return feedback_list
            
        except OperationFailure as e:
            logger.error(f"Database error retrieving feedback: {e}")
            raise

    @staticmethod
    async def mark_as_processed(feedback_id: str, category: str = None) -> bool:
        """
        Mark feedback as processed with optional categorization.

        Args:
            feedback_id: MongoDB document ID
            category: Optional feedback category
            
        Returns:
            bool: True if update successful
        """
        try:
            update = {
                "$set": {
                    "processed": True,
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
            }
            if category:
                update["$set"]["category"] = category

            result = db.feedback.update_one({"id": feedback_id}, update)
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error marking feedback as processed: {e}")
            return False


class TaskManager:
    """Manages CRUD operations for tasks in MongoDB"""
    
    @staticmethod
    def load_tasks() -> Dict[str, List[Dict[str, Any]]]:
        """
        Load all tasks from storage.
        
        Returns:
            Dict containing list of tasks with MongoDB _id removed
        
        Raises:
            OperationFailure: If MongoDB query fails
        """
        try:
            tasks = list(db.tasks.find())
            return {"tasks": [{k:v for k,v in task.items() if k != '_id'} for task in tasks]}
        except OperationFailure as e:
            logger.error(f"Failed to load tasks: {e}")
            raise

    @staticmethod
    def save_tasks(tasks_data: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Save tasks to storage, replacing existing ones.
        
        Args:
            tasks_data: Dictionary containing list of tasks to save
            
        Raises:
            OperationFailure: If MongoDB operation fails
        """
        if not tasks_data.get("tasks"):
            return
            
        try:
            with db.client.start_session() as session:
                with session.start_transaction():
                    db.tasks.delete_many({}, session=session)
                    db.tasks.insert_many(tasks_data["tasks"], session=session)
        except OperationFailure as e:
            logger.error(f"Failed to save tasks: {e}")
            raise

    @staticmethod
    def add_task(company: str, lesson_key: str, description: str, requirements: list) -> dict:
        """
        Add a new task with auto-incrementing ID.
        
        Args:
            company: Company name
            lesson_key: Lesson identifier
            description: Task description
            requirements: Optional list of requirements
            
        Returns:
            Newly created task dictionary
            
        Raises:
            OperationFailure: If MongoDB operation fails
        """
        try:
            # Get highest existing task ID
            last_task = db.tasks.find_one(sort=[("task_id", -1)])
            next_id = (last_task["task_id"] + 1) if last_task else 1
            
            task = {
                "task_id": next_id,
                "company": company,
                "lesson": lesson_key,
                "description": description,
                "requirements": requirements,
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            }
            
            result = db.tasks.insert_one(task)
            if result.acknowledged:
                logger.info(f"Task #{next_id} created for lesson {lesson_key}")
                return task
            return None
            
        except OperationFailure as e:
            logger.error(f"Failed to create task: {e}")
            raise

    @staticmethod
    def get_tasks_for_lesson(lesson_key: str) -> List[Dict[str, Any]]:
        """
        Get active tasks for a specific lesson.
        
        Args:
            lesson_key: Lesson identifier
            
        Returns:
            List of active tasks for the lesson
            
        Raises:
            OperationFailure: If MongoDB query fails
        """
        try:
            tasks = list(db.tasks.find({
                "lesson": lesson_key,
                "is_active": True
            }))
            return [{k:v for k,v in task.items() if k != '_id'} for task in tasks]
        except OperationFailure as e:
            logger.error(f"Failed to get tasks for lesson {lesson_key}: {e}")
            raise

    @staticmethod
    def deactivate_task(task_id: int) -> bool:
        """
        Deactivate a task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was deactivated, False if not found
            
        Raises:
            OperationFailure: If MongoDB update fails
        """
        try:
            # Fix: Changed "id" to "task_id" in query to match our schema
            result = db.tasks.update_one(
                {"task_id": task_id},  # Changed from "id" to "task_id"
                {"$set": {"is_active": False}}
            )
            success = result.modified_count > 0
            if success:
                logger.info(f"Task #{task_id} deactivated successfully")
            else:
                logger.warning(f"No task found with ID {task_id}")
            return success
        except OperationFailure as e:
            logger.error(f"Failed to deactivate task {task_id}: {e}")
            raise




def format_task_report(task):
    """Helper function to format task details without f-strings"""
    status = "🟢 Active" if task["is_active"] else "🔴 Inactive"
    lines = [
        f"Task #{task['id']} ({status})",
        f"Company: {task['company']}",
        f"Lesson: {task['lesson']}",
        f"Description: {task['description']}"
    ]
    
    if task["requirements"]:
        lines.append("Requirements:")
        for req in task["requirements"]:
            lines.append(f"- {req}")
    
    return "\n".join(lines)



async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to add a new task"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    usage = (
        "To add a task, use the following format:\n"
        "/addtask lesson_key\n"
        "Company Name\n"
        "Task Description\n"
        "Requirement 1\n"
        "Requirement 2\n"
        "...\n\n"
        "Example:\n"
        "/addtask lesson_2\n"
        "TechStartup Inc\n"
        "Design an onboarding flow for our mobile app\n"
        "- Experience with UX design\n"
        "- Knowledge of mobile design patterns"
    )

    try:
        if not update.message or not update.message.text:
            await update.message.reply_text(usage)
            return
            
        lines = update.message.text.split('\n')
        if len(lines) < 3:
            await update.message.reply_text(usage)
            return

        # Parse command and lesson key
        cmd_parts = lines[0].split()
        if len(cmd_parts) != 2:
            await update.message.reply_text(usage)
            return
            
        lesson_key = cmd_parts[1]
        
        # Validate lesson key
        if lesson_key not in lessons:
            await update.message.reply_text(f"Invalid lesson key. Available lessons: {', '.join(lessons.keys())}")
            return

        company = lines[1]
        description = lines[2]
        requirements = lines[3:] if len(lines) > 3 else []

        # Add the task
        task = TaskManager.add_task(company, lesson_key, description, requirements)
        
        if task:
            confirmation = f"""
✅ Task #{task['task_id']} added successfully!

📝 Task Details:
Lesson: {task['lesson']}
Company: {task['company']}
Description: {task['description']}
"""
            if task['requirements']:
                confirmation += "\nRequirements:\n" + "\n".join(f"- {req}" for req in task['requirements'])
            
            await update.message.reply_text(confirmation)
        else:
            await update.message.reply_text("Failed to create task. Please try again.")

    except Exception as e:
        logger.error(f"Error adding task: {e}")
        await update.message.reply_text("Error creating task. Please check the format and try again.")



async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all tasks with IDs"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        tasks = list(db.tasks.find())
        if not tasks:
            await update.message.reply_text("No tasks found.")
            return

        report = "📋 All Tasks:\n\n"
        for task in tasks:
            status = "🟢 Active" if task["is_active"] else "🔴 Inactive"
            report += f"Task #{task['task_id']} ({status})\n"
            report += f"Lesson: {task['lesson']}\n"
            report += f"Company: {task['company']}\n"
            report += f"Description: {task['description']}\n"
            if task["requirements"]:
                report += "Requirements:\n" + "\n".join(f"- {req}" for req in task["requirements"])
            report += "\n\n"

        await update.message.reply_text(report)

    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        await update.message.reply_text("Error retrieving tasks. Please try again.")

async def deactivate_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to deactivate a task"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Command format: /deactivatetask task_id
        task_id = int(context.args[0])
        TaskManager.deactivate_task(task_id)
        await update.message.reply_text(f"Task #{task_id} has been deactivated.")
    except (IndexError, ValueError):
        await update.message.reply_text("Please provide a valid task ID: /deactivatetask <task_id>")



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

# Flask routes for viewing journals
@app.route('/')
def home():
    return "Bot is running!"

@app.route('/journals/<user_id>')
def view_journal(user_id):
    # Convert user_id to int since it comes as string from URL
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID"}), 400
        
    journal = db.journals.find_one({"user_id": user_id})
    if journal:
        # Remove MongoDB's _id field before returning
        journal.pop('_id', None)
        return jsonify(journal)
    return jsonify({"error": "Journal not found"}), 404

@app.route('/journals')
def list_journals():
    journals = list(db.journals.find())
    # Remove MongoDB's _id field from each journal
    for journal in journals:
        journal.pop('_id', None)
    return jsonify(journals)



@app.route('/health')
async def health_check():
    """Health check endpoint"""
    try:
        # Test DB connection
        await asyncio.to_thread(db.users.find_one)
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "db": "connected"
        }, 200
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 500



async def keep_warm():
    """Periodic warm-up check"""
    try:
        await asyncio.to_thread(db.users.find_one)
        logger.debug("Warm-up successful")
    except Exception as e:
        logger.error(f"Warm-up failed: {e}")



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


# Define the lessons and steps
lessons = {
    "lesson_1": {
        "text": """🌟 Lesson 1 - Welcome

Hello and welcome! 👋

We're excited to help you learn how to build and grow products by leveraging communities. Here's how this will work:

You'll complete a series of tasks designed to teach mental models for building your own processes. These mental models include:

- Design Thinking 🎨
- Business Model Thinking 💼
- Market Thinking 📈
- User Thinking 👤
- Agile Project Thinking 🚀

✅ As you go through this:
- Think about other challenges you'd like to tackle.
- How can you apply these mental models to other areas of your life or work?

Let's start with Design Thinking! Ready? Click to continue. 📝""",
        "next": "lesson_2"
    },
    "lesson_2": {
        "text": """🎨 Lesson 2 - Design Thinking

Welcome to Design Thinking! 🎉

In this lesson, we'll work on improving the gift-giving experience for someone. You’ll learn how to understand their needs, define the problem, and come up with creative solutions.

✅ Why This Matters:
- You can use this process to improve any experience—not just gift-giving.
- It’s a powerful way to solve real-world problems by focusing on the user’s perspective.

Here's the 5-step breakdown:
1. Empathise: Understand your user's perspective and feelings. 🤝
2. Define: Identify the core problem or challenge. 🎯
3. Ideate: Brainstorm creative solutions. 💡
4. Prototype: Develop an initial version of your solution. 🛠️
5. Test: Get user feedback and refine your ideas. 🔄

Ready to dive in? Tap to begin! 📝""",
        "next": "lesson_2_step_1"
    },
    "lesson_2_step_1": {
        "text": """🤝 Step 1: Empathise

Understanding your user is key! To start, find someone you can interview. This could be a friend, sibling, or colleague. They will be your "user" throughout this exercise.

✅ Prep Task:
We are going to be working on improving the gift-giving experience for someone, that is to help them come up with better ways to give gifts. You can use this in any other situation or experience you want to improve.

1. Get a notebook or voice recorder to capture their responses.
2. Ask about their last gift-giving experience:
   - "What happened?"
   - "How did you choose the gift?"
   - "What was hard or easy about the process?"

Note interesting points. Share one insight you found surprising! 📝""",
        "next": "lesson_2_step_2"
    },
    "lesson_2_step_2": {
        "text": """🔍 Step 2: Research Some More

Follow up and dig deeper! Ask more questions about responses you found interesting. Use open-ended questions like "Why was that challenging?" or "How did that make you feel?"

✅ Task:
- Ask more questions about responses you found interesting.

Extra Resource: The 5 Whys
The 5 Whys is a simple tool to uncover the root cause of a problem. Ask "Why?" five times to dig deeper.

Example:
1. Why is gift-giving stressful? – I don’t know what to buy.
2. Why don’t you know? – I don’t know what they like.
3. Why don’t you know their interests? – We don’t talk much.
4. Why don’t you talk? – We’re always busy.
5. Why are you busy? – We don’t prioritize time together.

Root Cause: Lack of quality time.

Use this to uncover deeper insights!

Reply with one new insight you gained during this follow-up 📝""",
        "next": "lesson_2_step_3"
    },
    "lesson_2_step_3": {
        "text": """🎯 Step 3: Define

Let’s clarify the problem. Using your notes, create a concise problem statement.

✅ Tasks:
1. Write a Needs List: What was your user trying to accomplish?
   - What were they trying to do by going through that experience? What does gift giving do for them? Needs should be verbs.
2. Write an Insights List: What stood out to you during the interview?
   - These are the things you noticed would be helpful in improving that experience for your user.
3. Combine items in both the Needs List and the Insights List to craft a Problem Statement:
   - Example: "All needs a way to make the most of his time (Need), but he struggles with managing it effectively (Insight)."

Here’s a template you can use by filling in the blanks:
- [UserName] needs/wants a way to [user need], surprisingly // because // but [insight].

Reply with your problem statement for feedback 📝""",
        "next": "lesson_2_step_4"
    },
    "lesson_2_step_4": {
        "text": """💡 Step 4: Ideate

Time to get creative! Brainstorm possible solutions to the problem you defined.

✅ Tasks:
1. Write down at least 3 possible solutions (apps, services, or creative approaches).

Here are quick ideation techniques to spark creativity:
1. Steal Like an Artist
   - Look at successful products/services and adapt their ideas
   - Combine features from different sources
   - Add your unique twist
2. Generate Ideas Like a Pro
   - Observe how people solve similar problems
   - Try quick prototypes
   - Test and refine based on feedback

Reply with your list of ideas 📝""",
        "next": "lesson_2_step_5"
    },
    "lesson_2_step_5": {
        "text": """🛠️ Step 5: Prototype

Bring your idea to life! Create a simple prototype of your solution. You can use:
- Paper sketch
- Digital wireframe
- Physical mockup

✅ Tasks:
- Share a brief description of your prototype.

Quick prototyping tips:
- Start rough, it doesn't have to look good yet, focus on core features
- Label the key parts clearly
- Show how users would interact with it
- Keep it simple and easy to test

Reply with a description of your prototype 📝""",
        "next": "lesson_2_step_6"
    },
    "lesson_2_step_6": {
        "text": """🔄 Step 6: Test and Improve

Refine your idea with feedback! This is an ongoing process.

1. Show your prototype to your user.
2. Ask:
   - "What works well for you?"
   - "What doesn’t work or feels unclear?"

✅ Task: Use their feedback to refine your prototype.

Repeat this process as needed, but don’t aim for perfection—focus on real-world feedback! You are not looking to validate your solution, you just want feedback.

Reply with one key improvement you made based on testing 📝""",
        "next": "lesson_2_congratulations"
    },
    "lesson_2_congratulations": {
        "text": """🎉 Congratulations!

You’ve completed the Design Thinking process! Remember, it’s a cycle: Empathise, Define, Ideate, Prototype, and Test repeatedly to create great solutions.

✅ Where Else Can You Use This?
- Think about other experiences you’d like to improve.
- Where else could you apply this research and design process?

Next Step: Lesson 3 - Business Modelling. Ready? Tap to proceed! 📝""",
        "next": "lesson_3"
    },
    "lesson_3": {
        "text": """💼 Lesson 3 - Business Modelling

Welcome to Business Modelling! 🎉

This lesson helps you transform your idea into a sustainable business by learning how to create, deliver, and capture value using the Business Model Canvas.

✅ Step 1: What is a Business Model?
A business model explains how your idea will create, deliver, and capture value. Think of it as the story of your business that answers:
1. Who are you serving?
2. What value do you offer them?
3. How do you deliver and sustain that value profitably?

Task: Write down your initial answers to these three questions for your idea. This will act as your starting point.

Reply with your answers 📝""",
        "next": "lesson_3_step_1"
    },
    "lesson_3_step_1": {
        "text": """📊 Step 1: What is a Business Model?

A business model explains how your idea will create, deliver, and capture value. Think of it as the story of your business that answers:
1. Who are you serving?
2. What value do you offer them?
3. How do you deliver and sustain that value profitably?

✅ Task: Write down your initial answers to these three questions for your idea. This will act as your starting point.

Reply with your answers 📝""",
        "next": "lesson_3_step_2"
    },
    "lesson_3_step_2": {
        "text": """📝 Step 2: Introduction to the Business Model Canvas

The Business Model Canvas is a visual tool to design, iterate, and test your business model. It has 9 building blocks:

- Customer Segments: Who are your customers? Define them clearly (e.g., demographics, behaviours).
- Value Proposition: What problem are you solving, and what makes your solution unique?
- Channels: How will you reach your customers (e.g., online platforms, retail stores)?
- Customer Relationships: How will you interact with and retain customers (e.g., personalised support)?
- Revenue Streams: How will your business make money (e.g., subscription, one-time sales)?
- Key Resources: What assets are critical for delivering your value (e.g., technology, talent)?
- Key Activities: What actions are essential to run your business (e.g., marketing, product development)?
- Key Partnerships: Who can help you achieve your goals (e.g., suppliers, collaborators)?
- Cost Structure: What are your major costs (e.g., production, marketing)?

✅ Task: Map out these 9 blocks for your idea using sticky notes or a digital tool. Don’t worry about perfection—just start brainstorming!

Reply with your initial canvas 📝""",
        "next": "lesson_3_step_3"
    },
    "lesson_3_step_3": {
        "text": """🛠️ Step 3: Prototyping Your Business Model

Prototyping isn’t just for products! Use the Business Model Canvas to test different ways your idea can become a business. For example:
- Experiment with Revenue Streams: Could you charge a subscription fee instead of a one-time purchase?
- Reimagine Channels: Would a mobile app or social media be more effective than traditional advertising?

💡 Tip: Think creatively! Some successful businesses use unexpected models, like offering free services to drive demand for paid add-ons (e.g., freemium models).

✅ Task: Create 2-3 variations of your Business Model Canvas to explore different approaches. Reply with your top variation for feedback! 📝""",
        "next": "lesson_3_step_4"
    },
    "lesson_3_step_4": {
        "text": """🔍 Step 4: Testing Your Model

Once you have a prototype, it’s time to test your assumptions. Focus on key questions like:
1. Do customers care about your value proposition?
2. Are they willing to pay for your solution?
3. Are your chosen channels effective?

💡 Tip: Use real-world feedback. Talk to potential customers, test marketing campaigns, or run small-scale pilots.

✅ Task: Share one key insight you gained from testing and any changes you made to your business model. 📝""",
        "next": "lesson_3_step_5"
    },
    "lesson_3_step_5": {
        "text": """🌍 Step 5: Navigating the Business Environment

Your business doesn’t exist in isolation. Use these steps to map your environment:
- Market Forces: Who are your competitors? What are the trends?
- Key Trends: Are there emerging technologies or regulations that could impact you?
- Industry Forces: How is your industry evolving? What partnerships can you leverage?
- Macroeconomic Forces: What global factors (e.g., economic shifts) might affect your model?

✅ Task: Write down one opportunity and one threat from your environment. How can your business model adapt to address them? 📝""",
        "next": "lesson_3_step_6"
    },
    "lesson_3_step_6": {
        "text": """📖 Step 6: Telling Your Story

A great business model deserves a compelling story. Present your model clearly by:
1. Starting with your customer and their problem.
2. Showing how your value proposition solves their problem.
3. Explaining how your business captures and sustains value.

💡 Tip: Use examples and data to make your story relatable and credible.

✅ Task: Create a short pitch (3-5 sentences) based on your Business Model Canvas. Reply with your pitch for feedback! 📝""",
        "next": "lesson_3_congratulations"
    },
    "lesson_3_congratulations": {
        "text": """🎉 Congratulations!

You’ve learned how to turn your idea into a sustainable business model.

✅ Where Else Can You Use This?
- Think about other ideas or projects you’d like to model.
- How can you apply the Business Model Canvas to other ventures?

Next Step: Lesson 4 - Market Thinking. Ready? Tap to continue! 📝""",
        "next": "lesson_4"
    },
    "lesson_4": {
        "text": """📈 Lesson 4 - Market Thinking

Welcome to Market Thinking! 🌟

This lesson is all about helping you understand how your product fits into the broader market and scales to millions (or billions) in revenue. We’ll explore Brian Balfour’s Four Fit Framework in detail to ensure your product thrives.

✅ Step 1: Build on Your Product-Market Fit
In Lesson 2, you focused on deeply understanding your user’s problem. Now, take what you’ve learned and connect it to your product’s market.

Quick Recap: Product-Market Fit means solving a pressing problem for a specific group of people. Signs of strong fit include enthusiastic feedback, repeated usage, and word-of-mouth referrals.

Example: Dropbox achieved Product-Market Fit by solving the universal problem of file sharing with a simple, user-friendly solution.

Task: Write down the specific group of users your product is designed for and how your solution addresses their core pain points. Reply with your notes 📝""",
        "next": "lesson_4_step_1"
    },
    "lesson_4_step_1": {
        "text": """🎯 Step 1: Build on Your Product-Market Fit

In Lesson 2, you focused on deeply understanding your user’s problem. Now, take what you’ve learned and connect it to your product’s market.

Quick Recap: Product-Market Fit means solving a pressing problem for a specific group of people. Signs of strong fit include enthusiastic feedback, repeated usage, and word-of-mouth referrals.

Example: Dropbox achieved Product-Market Fit by solving the universal problem of file sharing with a simple, user-friendly solution.

✅ Task: Write down the specific group of users your product is designed for and how your solution addresses their core pain points. Reply with your notes 📝""",
        "next": "lesson_4_step_2"
    },
    "lesson_4_step_2": {
        "text": """📡 Step 2: Market-Channel Fit

Your product needs the right channels to reach its market effectively. Channels can include:
- IM-based platforms: Bots or tools integrated into messaging apps.
- Social media integrations: Like how Shopify connects with Instagram and YouTube to showcase products.

💡 Tip: The best channels align with how your target users already behave.

Example: Facebook grew by tapping into college campuses initially—targeting a concentrated, accessible audience.

✅ Task: List 3-5 channels your target users are most active on. Think creatively about where they interact (e.g., social media, apps, physical spaces). Reply with your list 📝""",
        "next": "lesson_4_step_3"
    },
    "lesson_4_step_3": {
        "text": """💰 Step 3: Channel-Model Fit

Your chosen channels must be profitable and align with your revenue model.

Example: Shopify’s partnerships with influencers work well because they drive traffic to stores, supporting Shopify’s subscription-based revenue model.

✅ Tasks:
1. Calculate your Customer Acquisition Cost (CAC). How much does it cost to acquire one customer via each channel?
2. Compare CAC with your Average Revenue Per User (ARPU). Is this channel profitable?

💡 Tip: If CAC is too high, focus on organic channels like referrals or SEO.

Reply with your calculations and insights 📝""",
        "next": "lesson_4_step_4"
    },
    "lesson_4_step_4": {
        "text": """💳 Step 4: Model-Market Fit

Your revenue model must fit your market's behaviour and spending habits.

Example: Netflix succeeds because its subscription model aligns with consumer habits of binge-watching and predictable monthly budgets.

✅ Tasks:
1. Research your market's spending habits. Are they price-sensitive or willing to pay for convenience?
2. Test pricing models. For example, experiment with free trials or tiered pricing.

💡 Tip: Use feedback from early adopters to refine your pricing strategy.

Reply with your findings 📝""",
        "next": "lesson_4_step_5"
    },
    "lesson_4_step_5": {
        "text": """🚀 Step 5: Putting It All Together

Your Growth Plan: With insights from each fit, craft a clear growth strategy:
1. Who are your customers?
2. What channels will you use to reach them?
3. How will you generate revenue and scale sustainably?

✅ Task: Create a 5-sentence summary of your fits and growth plan. Reply with your summary 📝""",
        "next": "lesson_4_congratulations"
    },
    "lesson_4_congratulations": {
        "text": """🎉 Congratulations!

You've learned how to align your product with its market and channels for scalable growth.

✅ Where Else Can You Use This?
- Think about other products or services you'd like to scale.
- How can you apply the Four Fit Framework to other markets?

Next Step: Lesson 5 - User Thinking. Ready? Tap to continue! 📝""",
        "next": "lesson_5"
    },
    "lesson_5": {
        "text": """👤 Lesson 5 - User Thinking

Welcome to User Thinking! 🧠

Understanding why people do what they do and how they think is essential to building products they love. This lesson introduces user psychology and behavior, equipping you with tools to create innovative, user-centered solutions.

✅ What You’ll Learn:
- How emotions influence actions and decisions.
- How to use the Hooked Model to design habit-forming products.

Ready to dive in? Let’s get started! 📝""",
        "next": "lesson_5_step_1"
    },
    "lesson_5_step_1": {
        "text": """😊 Step 1: Understanding Emotions

Emotions drive decisions. Learning how emotions influence behavior is key to designing better experiences.

Key Insights from Research:
1. Emotions and Decision-Making:
   - Emotions are integral to rational thinking. Studies show that people with damage to the amygdala (the part of the brain that regulates emotions) struggle to make even basic decisions. This highlights that decisions are not purely logical but are deeply influenced by emotions.
   - Emotional Intelligence (EI) is the ability to perceive, understand, and manage emotions. It helps us prioritize what truly matters and build healthy relationships.

2. Emotions in Action:
   - Negative emotions like loneliness, boredom, or dissatisfaction often trigger specific behaviors. For example, people check social media when they feel lonely or Google when they feel uncertain.
   - Positive emotions, like happiness, can make people more social and creative, while anxiety can help focus attention on immediate tasks.

✅ Task: Reflect on how emotions influence your own decisions. Write down one example of a decision you made recently that was driven by an emotion (e.g., buying something because it made you happy or avoiding a task because it caused anxiety).

Reply with your example 📝""",
        "next": "lesson_5_step_2"
    },
    "lesson_5_step_2": {
        "text": """🎣 Step 2: Introducing the Hooked Model

The Hooked Model is a framework for creating habit-forming products. It consists of four phases: Trigger, Action, Reward, and Investment.

Key Concepts:
1. Triggers:
   - External Triggers: These are cues in the environment, like notifications or ads, that prompt users to take action.
   - Internal Triggers: These are emotions or situations that drive users to seek a solution. For example, feeling bored might trigger someone to open a social media app.

2. Action:
   - The simplest behavior done in anticipation of a reward. For example, scrolling through a feed or clicking a button.
   - According to BJ Fogg’s Behavior Model, for an action to occur, users need sufficient motivation, ability, and a trigger.

3. Variable Reward:
   - Rewards that are unpredictable keep users engaged. There are three types of variable rewards:
     - Rewards of the Tribe: Social rewards, like likes or comments on social media.
     - Rewards of the Hunt: The search for resources or information, like scrolling through a news feed.
     - Rewards of the Self: Intrinsic rewards, like the satisfaction of completing a task or leveling up in a game.

4. Investment:
   - Users invest time, data, or effort into a product, which increases the likelihood of them returning. For example, building a profile or saving content creates value that keeps users coming back.

✅ Task:
Think of a product you use habitually (e.g., a social media app or a game). Identify one internal trigger, one action, and one variable reward that keeps you engaged.

Reply with your observations 📝""",
        "next": "lesson_5_step_3"
    },
    "lesson_5_step_3": {
        "text": """🛠️ Step 3: Applying the Hooked Model

Let’s apply the Hooked Model to your product idea.

✅ Tasks:
1. Identify the Internal Trigger:
   - What emotion or situation will prompt users to use your product? (e.g., boredom, loneliness, stress).

2. Define the Action:
   - What is the simplest behavior users will take to get a reward? (e.g., clicking a button, scrolling, or typing).

3. Design the Reward:
   - What variable reward will users receive? (e.g., social validation, new information, or a sense of accomplishment).

4. Encourage Investment:
   - How can users invest in your product to increase its value? (e.g., saving content, building a profile, or earning points).

Reply with your ideas 📝""",
        "next": "lesson_5_step_4"
    },
    "lesson_5_step_4": {
        "text": """🟢 Step 4: Case Study - Amazon’s Alexa

Let’s learn from a real-world example. Amazon’s Alexa uses behavior design to influence user habits.

Key Tactics:
1. Triggers: Alexa uses both external triggers (e.g., voice commands) and internal triggers (e.g., the desire for convenience or entertainment).
2. Actions: The simplest action is speaking a command, which requires minimal effort.
3. Rewards: Alexa provides variable rewards, such as playing music, answering questions, or controlling smart home devices.
4. Investment: Users invest in Alexa by setting up routines, adding skills, and connecting devices, which increases the product's value over time.

✅ Task:
Identify one tactic Alexa uses that you could apply to your own product.

Reply with your observation 📝""",
        "next": "lesson_5_step_5"
    },
    "lesson_5_step_5": {
        "text": """🧠 Step 5: A Deeper Dive into Behavior Models

To master persuasive design, let’s explore BJ Fogg’s Behavior Model in more detail.

Key Concepts:
1. Behavior = Motivation + Ability + Trigger:
   - For a behavior to occur, users must have sufficient motivation, the ability to perform the action, and a trigger to prompt them.

2. Motivation:
   - Users are motivated by seeking pleasure, avoiding pain, seeking hope, avoiding fear, and seeking social acceptance.

3. Ability:
   - To increase the likelihood of a behavior, make it easier to do. This can involve reducing the time, cost, or effort required.

4. Triggers:
   - Triggers must be well-timed and relevant to the user’s current state of motivation and ability.

✅ Task:
Reflect on your product. What is one way you can increase users’ motivation or ability to take the desired action?

Reply with your idea 📝""",
        "next": "lesson_5_congratulations"
    },
    "lesson_5_congratulations": {
        "text": """🎉 Congratulations!

You now understand how emotions and behavior models influence user decisions, giving you tools to create products that resonate deeply with your audience.

✅ Where Else Can You Use This?
- Think about other user behaviors you’d like to understand.
- How can you apply the Hooked Model or BJ Fogg’s Behavior Model to other products?

Next Step: Lesson 6 - Agile Project Thinking. Ready? Tap to continue! 📝""",
        "next": "lesson_6"
    },
    "lesson_6": {
        "text": """🚀 Lesson 6 - Project Thinking

Welcome to Project Thinking! 🛠️

This lesson combines principles from Agile and traditional project management to help you execute your business ideas efficiently and effectively.

✅ What You’ll Learn:
- How to scope and plan your work.
- How to use milestones and tasks to track progress.
- How to prioritise, batch, and review work for continuous improvement.

Ready to start? Tap to dive in! 📝""",
        "next": "lesson_6_step_1"
    },
    "lesson_6_step_1": {
        "text": """📜 Step 1: Agile Methodologies Overview

Agile methodologies were born from the Manifesto for Agile Software Development (https://agilemanifesto.org/). They emphasise:
- Individuals and interactions over processes and tools.
- Working software over comprehensive documentation.
- Customer collaboration over contract negotiation.
- Responding to change over following a plan.

✅ Task: Reflect on how these values apply to your project or work. Reply with one Agile value you want to implement 📝""",
        "next": "lesson_6_step_2"
    },
    "lesson_6_step_2": {
        "text": """📋 Step 2: Scope Your Work

Understand your work package. Scoping defines what needs to be delivered and why.

✅ Task: Answer these questions:
1. What is to be created and delivered by completing this work?
2. What is the purpose of the work?

Reply with your answers to move forward 📝""",
        "next": "lesson_6_step_3"
    },
    "lesson_6_step_3": {
        "text": """📅 Step 3: Create Milestones

Break your work into smaller, manageable parts. Milestones are clear checkpoints that show progress.

✅ Task:
1. What are the parts of the project or activities that will make it complete?
2. List them in the order they need to be done.

Reply with your milestones 📝""",
        "next": "lesson_6_step_4"
    },
    "lesson_6_step_4": {
        "text": """📝 Step 4: Define Tasks

Break milestones into actionable steps. Tasks should be specific and achievable.

✅ Task:
1. What specific tasks need to be done to achieve each milestone?
2. What resources or skills will you need to complete these tasks?

Reply with a list of tasks for your first milestone 📝""",
        "next": "lesson_6_step_5"
    },
    "lesson_6_step_5": {
        "text": """📊 Step 5: Prioritise Tasks

Focus on what matters most. Task prioritisation ensures efficient progress.

✅ Task: Arrange your tasks in order of dependency:
1. Which tasks must be completed first?
2. Which tasks can be done simultaneously?

Reply with your prioritised task list 📝""",
        "next": "lesson_6_step_6"
    },
    "lesson_6_step_6": {
        "text": """📆 Step 6: Create Sprints

Batch tasks into weekly sprints. Sprints help you focus on delivering results incrementally.

✅ Task:
1. Assign each task a completion time.
2. Group tasks into weekly sprints based on priority and available time.

Reply with your sprint plan for the first week 📝""",
        "next": "lesson_6_step_7"
    },
    "lesson_6_step_7": {
        "text": """🔄 Step 7: Review and Reflect

Continuous improvement is key. At the end of each week, review your progress and plan for the next.

✅ Task: Reflect on these questions:
1. What did I complete this week?
2. What challenges or blockers did I face?
3. What can I improve next week?

Reply with your answers to close the sprint 📝""",
        "next": "lesson_6_congratulations"
    },
    "lesson_6_congratulations": {
        "text": """🎉 Congratulations!

You’ve learned how to scope, plan, and execute your work efficiently using Agile principles.

✅ Where Else Can You Use This?
- Think about other projects or tasks you’d like to manage more effectively.
- How can you apply Agile methodologies to other areas of your life or work?

This concludes the course! Ready to apply what you’ve learned? Reply to share your next steps! 📝""",
        "next": None
    }
}



# Track user progress
user_data = {}

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



async def send_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_key: str) -> None:
    """Send lesson content with progress info and tasks"""
    try:
        chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
        
        # Update progress
        UserManager.update_progress(chat_id, lesson_key)
        
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
            
            # Add available tasks
            available_tasks = TaskManager.get_tasks_for_lesson(lesson_key)
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
            
    except Exception as e:
        logger.error(f"Error sending lesson: {str(e)}")
        # Send simplified message on parsing error
        await context.bot.send_message(
            chat_id=chat_id,
            text="Sorry, there was an error displaying this lesson. Please try /start to restart.",
            parse_mode=None
        )



async def handle_response(update: Update, context: CallbackContext):
    """Handle button responses."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press to remove loading state

    next_step = query.data
    if next_step and next_step in lessons:  # Check if next_step exists in lessons
        user_data[query.message.chat_id] = next_step
        await send_lesson(update, context, next_step)
    else:
        await query.edit_message_text(text="Please reply with your input to proceed.")



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



async def handle_message(update: Update, context: CallbackContext):
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



async def adminhelp_command(update: Update, context: CallbackContext):
    """Send a list of admin commands with descriptions."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    help_text = """
    🤖 Admin Commands:

    /users - View a list of all users
    /viewfeedback - View all feedback submitted by users
    /processfeedback <feedback_id> - Mark feedback as processed
    /addtask <lesson_key> - Add a task to a lesson
    /listtasks - List all tasks
    /deactivatetask <task_id> - Deactivate a task
    /adminhelp - Show this help message
    """
    await update.message.reply_text(help_text)

async def help_command(update: Update, context: CallbackContext):
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

async def setup_commands(bot):
    """Set up the bot commands in the client."""
    commands = [
        BotCommand("start", "Start or restart the learning journey"),
        BotCommand("journal", "View your learning journal"),
        BotCommand("help", "Show help information")
    ]
    await bot.set_my_commands(commands)



async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle feedback command"""
    await update.message.reply_text(
        "Please share your feedback or questions. Your message will be sent to our team."
    )
    context.user_data['expecting_feedback'] = True

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



# Admin Commands
async def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS



async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all users"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    users_list = list(db.users.find())
    
    report = "📊 Users Report:\n\n"
    for user in users_list:
        # Only count main lessons (not steps)
        completed_main_lessons = len([lesson for lesson in user.get('completed_lessons', []) 
                                      if lesson.count('_') == 1])  # Only counts lesson_X format
        report += f"👤 User: {user.get('username') or user.get('first_name')}\n"
        report += f"📝 Current Lesson: {user.get('current_lesson')}\n"
        report += f"✅ Completed: {len(user.get('completed_lessons', []))} lessons\n\n"
    
    await update.message.reply_text(report)



async def view_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view all feedback"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        feedback_list = FeedbackManager.get_all_feedback()
        if not feedback_list:
            await update.message.reply_text("No feedback found.")
            return
            
        report = "📬 Feedback Report:\n\n"
        for feedback in feedback_list:
            feedback_id = feedback.get('id', 'Unknown')  # Fetch feedback ID
            user_id = feedback.get('user_id', 'Unknown')
            
            # Add more detailed error handling for user info retrieval
            try:
                user = await UserManager.get_user_info(user_id)
                username = user.get('username', 'Unknown') if user else f"User {user_id}"
            except Exception as e:
                logger.error(f"Error fetching user info for {user_id}: {e}")
                username = f"User {user_id}"
            
            # Add feedback details with ID, status, and category
            report += f"🆔 Feedback ID: {feedback_id}\n"
            report += f"👤 From: {username} (ID: {user_id})\n"
            report += f"📅 Time: {feedback.get('timestamp', 'Unknown time')}\n"
            report += f"💭 Message: {feedback.get('feedback', 'No message content')}\n"
            report += f"📌 Status: {'✅ Processed' if feedback.get('processed') else '⏳ Pending'}"
            if feedback.get('category'):
                report += f" (Category: {feedback['category']})"
            report += "\n------------------------\n\n"
        
        # Split long reports into multiple messages if needed
        if len(report) > 4096:
            for i in range(0, len(report), 4096):
                await update.message.reply_text(report[i:i+4096])
        else:
            await update.message.reply_text(report)
            
    except Exception as e:
        logger.error(f"Error viewing feedback: {e}", exc_info=True)
        await update.message.reply_text("Error retrieving feedback. Please try again later.")





async def process_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to mark feedback as processed."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Extract feedback_id and category from the command arguments
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Usage: /processfeedback <feedback_id> [category]")
            return
        
        feedback_id = args[0]
        category = args[1] if len(args) > 1 else None

        # Mark feedback as processed
        success = await FeedbackManager.mark_as_processed(feedback_id, category)
        if success:
            await update.message.reply_text(f"✅ Feedback {feedback_id} has been marked as processed.")
        else:
            await update.message.reply_text(f"⚠️ Could not process feedback {feedback_id}. Please check the ID.")

    except Exception as e:
        logger.error(f"Error processing feedback: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while processing the feedback. Please try again.")




#put Flask in a separate function
def run_flask():
    port = int(os.getenv('PORT', 8080))  # Render prefers 8080
    app.run(host='0.0.0.0', port=port)



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
    
    try:
        # Initialize database
        logger.info("Attempting to connect to MongoDB...")
        global db
        logger.info("Using existing MongoDB connection.")
        
        # Initialize bot and create application instance if not exists
        if application is None:
            application = Application.builder().token(BOT_TOKEN).build()
            await application.initialize()
            # Add command handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("resume", resume_command))
            application.add_handler(CommandHandler("journal", get_journal))
            application.add_handler(CommandHandler("feedback", feedback_command))
            application.add_handler(CommandHandler("myfeedback", my_feedback_command))
            application.add_handler(CommandHandler("help", help_command))
            
            # Admin handlers
            application.add_handler(CommandHandler("adminhelp", adminhelp_command))
            application.add_handler(CommandHandler("users", list_users))
            application.add_handler(CommandHandler("viewfeedback", view_feedback))
            application.add_handler(CommandHandler("processfeedback", process_feedback_command))
            application.add_handler(CommandHandler("addtask", add_task_command))
            application.add_handler(CommandHandler("listtasks", list_tasks_command))
            application.add_handler(CommandHandler("deactivatetask", deactivate_task_command))

            # Message handlers
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
                BotCommand("feedback", "Send feedback or questions"),
                BotCommand("myfeedback", "View your feedback history"),
                BotCommand("help", "Show help information")
            ])

        # Set webhook in application
        if WEBHOOK_URL:
            webhook_path = f"{WEBHOOK_URL}"
            await application.bot.set_webhook(webhook_path)
            logger.info(f"Webhook set to {webhook_path}")
        else:
            logger.warning("WEBHOOK_URL environment variable not set. Webhook not configured.")
        return application
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


async def create_app():
    """Initialize the application"""
    global application
    
    # Initialize bot
    application = await main()
    await application.start()

    # Setup warm-up job
    scheduler.add_job(keep_warm, 'interval', minutes=10)
    scheduler.start()

    return app

async def start_app():
    """Start the Quart application"""
    port = int(os.getenv('PORT', 8080))
    await app.run_task(host='0.0.0.0', port=port)

if __name__ == "__main__":
    import asyncio
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = loop.run_until_complete(create_app())
    loop.run_until_complete(start_app())