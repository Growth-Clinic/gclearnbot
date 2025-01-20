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
            feedback_data = {
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
                logger.info(f"Feedback saved for user {user_id}")
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

            result = db.feedback.update_one({"_id": feedback_id}, update)
            return result.modified_count > 0

        except OperationFailure as e:
            logger.error(f"Error marking feedback as processed: {e}")
            raise


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
        "text": (
            "👋 Hello and welcome!\n\n"
            "We're excited to help you learn how to build and grow products by leveraging communities. Here's how this will work:\n\n"
            "✨ You'll complete a series of tasks designed to teach mental models for building your own processes. These mental models include:\n\n"
            "- 🧠 Design Thinking\n"
            "- 📊 Business Model Thinking\n"
            "- 🌍 Market Thinking\n"
            "- 👤 User Thinking\n"
            "- 🏗️ Agile Project Thinking\n\n"
            "Let's start with Design Thinking! Ready? Reply ✅ to continue."
        ),
        "next": "lesson_2"
    },
    "lesson_2": {
        "text": """🧠 Lesson 2: Design Thinking

👋 Welcome to Design Thinking! This lesson helps you learn and apply the 5-step process for understanding and solving user problems. Here's the breakdown:

1️⃣ Empathise: Understand your user's perspective and feelings
2️⃣ Define: Identify the core problem or challenge
3️⃣ Ideate: Brainstorm creative solutions
4️⃣ Prototype: Develop an initial version of your solution
5️⃣ Test: Get user feedback and refine your ideas

🌟 Exercise Focus: Redesign the experience of gift-giving for someone close to you (not the gift itself). Ready? Reply ✅ to begin.""",
        "next": "lesson_2_step_1"
    },
    "lesson_2_step_1": {
        "text": """🔍 Understanding your user is key! To start, find someone you can interview. This could be a friend, sibling, or colleague. They will be your "user" throughout this exercise.

✅ Prep Task:
1. Get a notebook or voice recorder to capture their responses.
2. Ask about their last gift-giving experience:
   - "What happened?"
   - "How did you choose the gift?"
   - "What was hard or easy about the process?"

📝 Note interesting points. Share one insight you found surprising!""",
        "next": "lesson_2_step_2"
    },
    "lesson_2_step_2": {
        "text": """💬 Follow up and dig deeper! Ask more questions about responses you found interesting. Use open-ended questions like "Why was that challenging?" or "How did that make you feel?"

🔥 Tip: Ask "Why?" multiple times until you uncover deeper feelings or emotions.

📚 Resource: Read this article on the 5 Whys (https://en.wikipedia.org/wiki/5_Whys) to understand why asking "Why" is so powerful in design.

Reply 📝 with one new insight you gained during this follow-up.""",
        "next": "lesson_2_step_3"
    },
    "lesson_2_step_3": {
        "text": """📌 Let's clarify the problem. Using your notes, create a concise problem statement. Here's how:

✅ Tasks:
1. Write a Needs List: What was your user trying to accomplish?
   - What were they trying to do by going through that experience. What does gift giving do for them. Needs should be verbs.
2. Write an Insights List: What stood out to you during the interview?
   - These are the things you noticed would be helpful in improving that experience for your user.
3. Combine items in both the Needs List and the Insights List to craft a Problem Statement:
   - Example: "Ali needs a way to make the most of his time (Need), but he struggles with managing it effectively (Insight)."

Here's a template you can use by filling in the blanks/[ text ]:
- [UserName] needs/wants a way to [user need], surprisingly // because // but [insight].

Reply ✏️ with your problem statement for feedback!""",
        "next": "lesson_2_step_4"
    },
    "lesson_2_step_4": {
        "text": """💡 Time to get creative! Brainstorm possible solutions to the problem you defined.

✅ Tasks:
1. Write down at least 3 possible solutions (apps, services, or creative approaches).
2. Need inspiration? Check out these resources:
   - How to Build Creative Confidence: https://youtu.be/16p9YRF0l-g
   - How to Generate Ideas: https://youtu.be/L1kbrlZRDvU
   - Develop an Eye for Design: https://medium.com/@kathleen_warner/how-to-develop-an-eye-for-design-c5a4c64bb26c
   - Stealing Your Way to Original Designs: https://danmall.com/posts/stealing-your-way-to-original-designs/

Reply 💡 with your list of ideas.""",
        "next": "lesson_2_step_5"
    },
    "lesson_2_step_5": {
        "text": """🛠️ Bring your idea to life! Use your top solution to create a simple prototype. Sketch it out on paper or use a free tool like MarvelApp (https://marvelapp.com/) to create an interactive wireframe.

✅ Tasks:
- Share a brief description or photo of your prototype.
- Need help? Check out this guide on UX Sketching: https://www.toptal.com/designers/ux/guide-to-ux-sketching

Reply 📷 with your prototype or its description.""",
        "next": "lesson_2_step_6"
    },
    "lesson_2_step_6": {
        "text": """🔄 Refine your idea with feedback! This is an ongoing process.

1. Show your prototype to your user.
2. Ask:
   - "What works well for you?"
   - "What doesn't work or feels unclear?"

✅ Task: Use their feedback to refine your prototype.

Repeat this process as needed, but don't aim for perfection---focus on real-world feedback! You are not looking to validate your solution, you just want feedback.

Reply 📝 with one key improvement you made based on testing.

🌟 Congratulations! You've completed the Design Thinking process! Remember, it's a cycle: Empathise, Define, Ideate, Prototype, and Test repeatedly to create great solutions.

Are you ready to move to Lesson 3 on Business Modelling? Reply ✅ to proceed!""",
        "next": "lesson_3"
    },
    "lesson_3": {
        "text": """📊 Lesson 3: Business Modelling

👋 Welcome to Business Modelling! This lesson introduces the Business Model Canvas, a strategic tool for creating and documenting business models. You'll apply this to the idea you worked on in the Design Thinking lesson.

🎥 Videos to Watch:
1. Quick Overview of the Business Model Canvas: https://www.youtube.com/watch?v=QoAOzMTLP5s
2. Getting From Business Idea to Business Model: https://www.youtube.com/watch?v=wwShFsSFb-Y
3. Visualising Your Business Model: https://www.youtube.com/watch?v=wlKP-BaC0jA
4. Prototyping Business Models: https://www.youtube.com/watch?v=iA5MVUNkSkM
5. Navigating Your Environment: https://www.youtube.com/watch?v=7O36YBn9x_4
6. Proving It: Testing Business Models: https://www.youtube.com/watch?v=-2gd_vhNYT4
7. Telling Your Story: https://www.youtube.com/watch?v=SshglHDKQCc

✅ Task: Watch the videos in order. Reply ✅ once done.""",
        "next": "lesson_3_step_2"
    },
    "lesson_3_step_2": {
        "text": """📖 The Business Model Canvas includes 9 key components:

- Value Proposition
- Customer Segments
- Revenue Streams
- Channels
- Cost Structure
- Key Activities
- Key Resources
- Key Partnerships
- Customer Relationships

✍️ Task: Take the idea you worked on during the Design Thinking lesson and begin filling in the Business Model Canvas. Focus on:
1️⃣ Value Proposition: What problem does your product solve?
2️⃣ Customer Segments: Who are you solving this problem for?

Reply 📝 with your notes for these two components.""",
        "next": "lesson_3_step_3"
    },
    "lesson_3_step_3": {
        "text": """🔄 A business model should evolve based on feedback and testing.

✅ Tasks:
1. Map your business's environment: Consider competitors, trends, and external factors that affect your model.
2. Test assumptions for each component of the Canvas. For example:
   - Are your target customers willing to pay for this solution?
   - Are the chosen channels effective for reaching them?

Reply 📝 with one insight or change you made based on your tests.""",
        "next": "lesson_3_step_4"
    },
    "lesson_3_step_4": {
        "text": """📜 The final step is crafting a compelling narrative. Your story should explain:
- What your product does.
- Why it's needed.
- How it creates value.

✅ Task: Use your notes from the Canvas to write a 3-sentence pitch for your product.

Reply 📜 with your pitch.

🌟 Congratulations! You've completed Lesson 3: Business Modelling. You now know how to create, refine, and present a business model.

🚀 Next Step: Lesson 4 - Market Thinking. Ready? Reply ✅ to continue!""",
        "next": "lesson_4"
    },
    "lesson_4": {
        "text": """🌍 Lesson 4: Market Thinking

👋 Welcome to Market Thinking! Understanding your market is critical for aligning your product with user needs and growth channels. This lesson will guide you through Brian Balfour's Four Fit Framework, a powerful approach to structuring your business for sustainable growth.

💡 Explore the Four Fit Framework:
1️⃣ Product-Market Fit: Does your product solve a key problem for your target users?
2️⃣ Market-Channel Fit: Are your chosen channels effective for reaching your market?
3️⃣ Channel-Model Fit: Do your channels align with your revenue model?
4️⃣ Model-Market Fit: Does your revenue model work well within your target market?

📚 Start with these essays:
- Why Product-Market Fit Isn't Enough: https://brianbalfour.com/essays/product-market-fit-isnt-enough
- Market-Product Fit: The Road to a $100M Company Doesn't Start with Product: https://brianbalfour.com/essays/market-product-fit
- Product-Channel Fit Will Make or Break Your Growth Strategy: https://brianbalfour.com/essays/product-channel-fit-for-growth
- Channel-Model Fit: Get Out of the ARPU-CAC Danger Zone: https://brianbalfour.com/essays/channel-model-fit-for-user-acquisition
- Model-Market Fit Threshold for Growth: https://brianbalfour.com/essays/model-market-fit-threshold-for-growth
- How The Four Fits Work Together: https://brianbalfour.com/essays/key-lessons-for-100m-growth
- HubSpot Growth Framework Case Study: https://brianbalfour.com/essays/hubspot-growth-framework-100m

🎥 Prefer videos? Watch summaries embedded in the essays for a quick overview. Reply ✅ when you've completed the first essay.""",
        "next": "lesson_4_step_2"
    },
    "lesson_4_step_2": {
        "text": """🔄 Task: Using the product idea from your Design Thinking lesson, answer these:

1️⃣ Who are your target users? Define their demographics, behaviour, and pain points.
2️⃣ What channels will you use to reach them? Consider online, offline, and hybrid channels.

📝 Reply with your answers for feedback.""",
        "next": "lesson_4_step_3"
    },
    "lesson_4_step_3": {
        "text": """📌 Task: Reflect on your answers and evaluate:

- Does your product align well with your market's needs?
- Are the chosen channels scalable and effective?
- Does your revenue model work seamlessly within this framework?

Reply 📝 with one insight or adjustment you've made to improve your fit.

🌟 Congratulations! You've completed Lesson 4: Market Thinking. You now have the tools to align your product with its market, channels, and revenue model for maximum growth.

🚀 Next Step: Lesson 5 - User Thinking. Ready? Reply ✅ to continue!""",
        "next": "lesson_5"
    },
    "lesson_5": {
        "text": """👤 Lesson 5: User Thinking

👋 Welcome to User Thinking! Understanding why people do what they do and how they think is essential to building products they love. This lesson introduces user psychology and behaviour, equipping you with tools to create innovative, user-centred solutions.

🔍 What You’ll Learn:
1️⃣ How emotions influence actions and decisions.
2️⃣ How to use the Hooked Model to design habit-forming products.

🌟 Ready to dive in? Reply ✅ to start!""",
        "next": "lesson_5_step_1"
    },
    "lesson_5_step_1": {
        "text": """💡 Emotions drive decisions. Learning how emotions influence behaviour is key to designing better experiences.

✅ Tasks:
1. Watch these videos:
   - How emotions are an integral part of thinking and decision making: https://youtu.be/weuLejJdUu0
   - How emotions define people’s decisions: https://youtu.be/1wup_K2WN0I
   - Why good design makes us happy: https://www.youtube.com/watch?v=RlQEoJaLQRA

Write down one insight from each video.

📝 Reply with your three insights to proceed.""",
        "next": "lesson_5_step_2"
    },
    "lesson_5_step_2": {
        "text": """🧠 Create habit-forming products. The Hooked Model combines triggers, actions, rewards, and investment to build user engagement.

✅ Tasks:
1. Watch this 30-minute summary: How to Build Habit-Forming Products Using The Hook Model and BJ Fogg’s Behaviour Model: https://www.youtube.com/watch?v=RR9PnPr529k
2. Download and complete exercises in this workbook: https://drive.google.com/file/d/0B27e0z0T2hi2NmI5S0tqdWIwWHk2RlNNTWFMUVBxWEdsN1VF/view?usp=sharing

📝 Reply with one key takeaway from the video and workbook.""",
        "next": "lesson_5_step_3"
    },
    "lesson_5_step_3": {
        "text": """📖 Learn from Alexa’s success. Behaviour design can influence user habits significantly.

✅ Tasks:
1. Read this case study: How Amazon’s Alexa design changes our behaviour: https://medium.com/behavior-design/the-secret-behind-alexas-success-3188d473199c
2. Identify one tactic Alexa uses that you could apply to your own product.

📝 Reply with your observation.""",
        "next": "lesson_5_step_4"
    },
    "lesson_5_step_4": {
        "text": """📚 Master persuasive design. Use behaviour models to influence how users interact with your product.

✅ Tasks:
1. Read this paper: A Behaviour Model for Persuasive Design: https://drive.google.com/file/d/1jHrV9Ur8YrG-i3VDA8_rw6NCMtCB97LO/view?usp=sharing
2. Reflect on how you can apply these principles to your product.

📝 Reply with one application idea for your product.

🌟 Congratulations! You've completed Lesson 5: User Thinking. You now understand user psychology and behaviour, giving you tools to create solutions that resonate deeply with your audience.

🚀 Next Step: Lesson 6 - Agile Project Thinking. Ready? Reply ✅ to continue!""",
        "next": "lesson_6"
    },
    "lesson_6": {
        "text": """🏗️ Lesson 6: Project Thinking

👋 Welcome to Project Thinking! This lesson combines principles from Agile and traditional project management to help you execute your business ideas efficiently and effectively.

🔍 What You’ll Learn:
1️⃣ How to scope and plan your work.
2️⃣ How to use milestones and tasks to track progress.
3️⃣ How to prioritise, batch, and review work for continuous improvement.

🌟 Ready to start? Reply ✅ to dive in!""",
        "next": "lesson_6_step_1"
    },
    "lesson_6_step_1": {
        "text": """📜 Agile methodologies were born from the Manifesto for Agile Software Development (https://agilemanifesto.org/). They emphasise:

- Individuals and interactions over processes and tools.
- Working software over comprehensive documentation.
- Customer collaboration over contract negotiation.
- Responding to change over following a plan.

✅ Task: Reflect on how these values apply to your project or work. Reply 📝 with one Agile value you want to implement.""",
        "next": "lesson_6_step_2"
    },
    "lesson_6_step_2": {
        "text": """📌 Understand your work package. Scoping defines what needs to be delivered and why.

✅ Task: Answer these questions:
1. What is to be created and delivered by completing this work?
2. What is the purpose of the work?

Reply 📝 with your answers to move forward.""",
        "next": "lesson_6_step_3"
    },
    "lesson_6_step_3": {
        "text": """🎯 Break your work into smaller, manageable parts. Milestones are clear checkpoints that show progress.

✅ Task:
1. What are the parts of the project or activities that will make it complete?
2. List them in the order they need to be done.

Reply 📝 with your milestones.""",
        "next": "lesson_6_step_4"
    },
    "lesson_6_step_4": {
        "text": """🛠️ Break milestones into actionable steps. Tasks should be specific and achievable.

✅ Task:
1. What specific tasks need to be done to achieve each milestone?
2. What resources or skills will you need to complete these tasks?

Reply 📝 with a list of tasks for your first milestone.""",
        "next": "lesson_6_step_5"
    },
    "lesson_6_step_5": {
        "text": """📋 Focus on what matters most. Task prioritisation ensures efficient progress.

✅ Task: Arrange your tasks in order of dependency:
1. Which tasks must be completed first?
2. Which tasks can be done simultaneously?

Reply 📝 with your prioritised task list.""",
    "next": "lesson_6_step_6"
    },
    "lesson_6_step_6": {
        "text": """⏳ Batch tasks into weekly sprints. Sprints help you focus on delivering results incrementally.

✅ Task:
1. Assign each task a completion time.
2. Group tasks into weekly sprints based on priority and available time.

Reply 📝 with your sprint plan for the first week.""",
        "next": "lesson_6_step_7"
    },
    "lesson_6_step_7": {
        "text": """🔄 Continuous improvement is key. At the end of each week, review your progress and plan for the next.

✅ Task: Reflect on these questions:
1. What did I complete this week?
2. What challenges or blockers did I face?
3. What can I improve next week?

Reply 📝 with your answers to close the sprint.

🌟 Congratulations! You’ve completed Lesson 6: Project Thinking. You now have a systematic way to scope, plan, and execute your work efficiently.

🚀 This concludes the course! Ready to apply what you’ve learned? Reply ✅ to share your next steps!,"""
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
            user_id = feedback.get('user_id', 'Unknown')
            
            # Add more detailed error handling for user info retrieval
            try:
                user = await UserManager.get_user_info(user_id)
                username = user.get('username', 'Unknown') if user else f"User {user_id}"
            except Exception as e:
                logger.error(f"Error fetching user info for {user_id}: {e}")
                username = f"User {user_id}"
            
            # Add more feedback details in the report
            report += f"From: {username} (ID: {user_id})\n"
            report += f"Time: {feedback.get('timestamp', 'Unknown time')}\n"
            report += f"Message: {feedback.get('feedback', 'No message content')}\n"
            report += f"Status: {'✅ Processed' if feedback.get('processed') else '⏳ Pending'}\n"
            report += "------------------------\n\n"
        
        # Split long reports into multiple messages if needed
        if len(report) > 4096:
            for i in range(0, len(report), 4096):
                await update.message.reply_text(report[i:i+4096])
        else:
            await update.message.reply_text(report)
            
    except Exception as e:
        logger.error(f"Error viewing feedback: {e}", exc_info=True)  # Added exc_info for better debugging
        await update.message.reply_text("Error retrieving feedback. Please try again later.")



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