from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
import certifi
from config.settings import Config
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List
from services.lesson_loader import load_lessons
import time
import asyncio


logger = logging.getLogger(__name__)
lessons = load_lessons()


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
