from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
import certifi
from config.settings import Config
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List
from services.content_loader import content_loader
from services.utils import extract_keywords_from_response
from services.lesson_helpers import get_lesson_structure, is_actual_lesson, get_total_lesson_steps
import time
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__) # Get logger instance


lessons = content_loader.load_content('lessons')


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

            # Ensure indices and collections exist
            if "user_skills" not in db.list_collection_names():
                db.create_collection("user_skills")
                db.user_skills.create_index("user_id", unique=True)
                logger.info("Created user_skills collection with index")
            
            if "learning_insights" not in db.list_collection_names():
                db.create_collection("learning_insights")
                db.learning_insights.create_index("user_id", unique=True)
                logger.info("Created learning_insights collection with index")
            
            # Ensure an index on user_id for journals collection
            db.journals.create_index("user_id")

            # Add indices for analytics
            db.journals.create_index([("entries.timestamp", -1)])
            db.learning_insights.create_index([("insights.timestamp", -1)])

            # Add platform support indices
            db.users.create_index([("user_id", 1), ("platform", 1)], unique=True)
            
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



class DataValidator:
    """Handles data validation for database operations"""
    
    @staticmethod
    def validate_user_data(user_data: Dict[str, Any]) -> bool:
        """
        Validate user data before saving.
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = {
            "user_id": str,
            "username": str,
            "first_name": str,
            "language_code": str,
            "joined_date": str,
            "platform": str
        }
        
        try:
            # Check required fields exist and are correct type
            for field, field_type in required_fields.items():
                if field not in user_data:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not isinstance(user_data[field], field_type) and user_data[field] is not None:
                    logger.error(f"Invalid type for field {field}")
                    return False
            
            # Validate timestamps
            if not isinstance(user_data.get("joined_date"), str):
                logger.error("Invalid joined_date format")
                return False
            
            # Validate platform field
            if user_data['platform'] not in ['telegram', 'slack']:
                logger.error("Invalid platform specified")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating user data: {e}")
            return False

    @staticmethod
    def validate_feedback_data(feedback_data: Dict[str, Any]) -> bool:
        """
        Validate feedback data before saving.
        
        Args:
            feedback_data: Dictionary containing feedback information
            
        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = {
            "id": int,
            "user_id": int,
            "feedback": str,
            "timestamp": (datetime, str),  # Can be either datetime or string
            "processed": bool
        }
        
        try:
            # Check required fields exist and are correct type
            for field, field_type in required_fields.items():
                if field not in feedback_data:
                    logger.error(f"Missing required field in feedback: {field}")
                    return False
                    
                # Handle fields that can be multiple types
                if isinstance(field_type, tuple):
                    if not isinstance(feedback_data[field], field_type[0]) and not isinstance(feedback_data[field], field_type[1]):
                        logger.error(f"Invalid type for feedback field {field}")
                        return False
                elif not isinstance(feedback_data[field], field_type):
                    logger.error(f"Invalid type for feedback field {field}")
                    return False
            
            # Validate feedback text is not empty
            if not feedback_data["feedback"].strip():
                logger.error("Empty feedback text")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating feedback data: {e}")
            return False

    @staticmethod
    def validate_task_data(task_data: Dict[str, Any]) -> bool:
        """Validate task data before saving."""
        try:
            required_fields = {
                "task_id": int,
                "company": str,
                "lesson": str,
                "description": str,
                "requirements": list,
                "is_active": bool
            }
            
            # Check required fields exist and are correct type
            for field, field_type in required_fields.items():
                if field not in task_data:
                    logger.error(f"Missing required field in task: {field}")
                    return False
                if not isinstance(task_data[field], field_type):
                    logger.error(f"Invalid type for task field {field}")
                    return False
            
            # Validate text fields are not empty
            if not task_data["company"].strip():
                logger.error("Empty company name")
                return False
            if not task_data["description"].strip():
                logger.error("Empty task description")
                return False
            
            # Validate lesson exists
            lessons = content_loader.load_content('lessons')
            if task_data["lesson"] not in lessons:
                logger.error(f"Invalid lesson in task: {task_data['lesson']}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating task data: {e}")
            return False

    @staticmethod
    def validate_journal_entry(entry: Dict[str, Any]) -> bool:
        """
        Validate journal entry before saving.
        
        Args:
            entry: Dictionary containing journal entry
            
        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = {
            "timestamp": str,
            "lesson": str,
            "response": str,
            "response_length": int
        }
        
        try:
            # Check required fields exist and are correct type
            for field, field_type in required_fields.items():
                if field not in entry:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not isinstance(entry[field], field_type):
                    logger.error(f"Invalid type for field {field}")
                    return False
            
            # Validate response is not empty
            if not entry["response"].strip():
                logger.error("Empty response")
                return False
            
            # Validate lesson exists
            if entry["lesson"] not in lessons:
                logger.error(f"Invalid lesson: {entry['lesson']}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating journal entry: {e}")
            return False


class UserManager:
    @staticmethod
    async def save_user_info(user, platform: str = 'telegram', email: str = None) -> Dict[str, Any]:
        """Save comprehensive user information when they start using the bot or link their email."""
        try:
            # Convert user_id to string for consistency across platforms
            user_id = str(user.id if platform == 'telegram' else user)

            user_data = {
                "user_id": user_id,
                "username": user.username if platform == 'telegram' else user.get('name', ''),
                "first_name": user.first_name if platform == 'telegram' else user.get('real_name', ''),
                "last_name": user.last_name or "",
                "language_code": user.language_code or "en",
                "joined_date": datetime.now(timezone.utc).isoformat(),
                "current_lesson": "lesson_1",
                "completed_lessons": [],
                "last_active": datetime.now(timezone.utc).isoformat(),
                "platform": platform,
                "progress_metrics": {
                    "total_responses": 0,
                    "average_response_length": 0,
                    "completion_rate": 0,
                    "last_lesson_date": None
                },
                "learning_preferences": {
                    "preferred_language": user.language_code or "en",
                    "notification_enabled": True
                }
            }

            # If the user provided an email, add it to their profile
            update_fields = {"$set": user_data}

            if email:
                update_fields["$set"]["email"] = email  # Store email
                update_fields["$set"]["chat_id"] = user_id  # Ensure chat_id is saved

            if not DataValidator.validate_user_data(user_data):
                logger.error(f"Invalid user data for user {user.id}")
                return None

            result = db.users.update_one(
                {"user_id": user_id, "platform": platform},
                update_fields,
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
    async def get_user_info(user_id: str, platform: str = 'telegram') -> Optional[Dict[str, Any]]:
        """
        Get user information from the database, including current lesson progress.
        
        Args:
            user_id: The user's Telegram ID
            
        Returns:
            Dictionary containing user information or None if not found
        """
        try:
            # Convert user_id to string if it's not already
            user_id = str(user_id)

            user_data = await asyncio.to_thread(
                db.users.find_one,
                {"user_id": user_id, "platform": platform}
            )
            
            if user_data:
                # Ensure `current_lesson` exists, default to lesson_1
                if "current_lesson" not in user_data:
                    user_data["current_lesson"] = "lesson_1"
                    await asyncio.to_thread(
                        db.users.update_one,
                        {"user_id": user_id, "platform": platform},
                        {"$set": {"current_lesson": "lesson_1"}}
                    )
                
                user_data.pop('_id', None)  # Remove MongoDB ID
                return user_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving user info: {e}", exc_info=True)
            return None
        
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by email.

        Args:
            email: The user's email

        Returns:
            Dictionary containing user information or None if not found
        """
        try:
            user_data = await asyncio.to_thread(
                db.users.find_one,
                {"email": email}
            )
            if user_data:
                user_data.pop("_id", None)  # Remove MongoDB ID
                return user_data
            return None

        except Exception as e:
            logger.error(f"Error retrieving user by email: {e}", exc_info=True)
            return None
        
    @staticmethod
    async def update_user_info(user_id: str, data: Dict[str, Any]) -> bool:
        """
        Update user data (e.g., email, progress, preferences).

        Args:
            user_id: The user's ID (Telegram chat_id or web user_id)
            data: The data to update

        Returns:
            True if update was successful, False otherwise
        """
        try:
            user_id = str(user_id)  # Ensure it's a string

            result = await asyncio.to_thread(
                db.users.update_one,
                {"user_id": user_id},
                {"$set": data},
                upsert=True
            )

            return result.modified_count > 0 or result.upserted_id is not None

        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
            return False

    @staticmethod
    def get_lesson_structure():
        """Helper method to understand lesson hierarchy"""
        lesson_structure = {}
        for key in lessons.keys():
            if "_step_" in key:
                main_lesson = key.split("_step_")[0]
                if main_lesson not in lesson_structure:
                    lesson_structure[main_lesson] = []
                lesson_structure[main_lesson].append(key)
        return lesson_structure

    @staticmethod
    async def update_user_progress(user_id: int, lesson_key: str) -> bool:
        """
        Update user's progress with enhanced metrics and proper step tracking.

        Args:
            user_id: The user's Telegram ID
            lesson_key: Current lesson identifier

        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Log the start of progress update
            logger.info(f"Starting progress update for user {user_id} to lesson {lesson_key}")

            if lesson_key not in lessons:
                logger.error(f"Invalid lesson key: {lesson_key}")
                return False

            # Get current user data
            user_data = await asyncio.to_thread(
                db.users.find_one,
                {"user_id": user_id}
            )

            if not user_data:
                logger.error(f"User {user_id} not found")
                return False

            # Only update if this is a new step
            current_lesson = user_data.get('current_lesson')
            if current_lesson == lesson_key:
                logger.info(f"User {user_id} already on lesson {lesson_key}")
                return True

            # Log the actual progression
            logger.info(f"User {user_id} moving from {current_lesson} to {lesson_key}")

            current_date = datetime.now(timezone.utc).isoformat()

            # Update completed lessons
            await asyncio.to_thread(
                db.users.update_one,
                {"user_id": user_id},
                {"$addToSet": {"completed_lessons": current_lesson}}
            )

            # Calculate completion metrics
            completed_lessons = user_data.get('completed_lessons', [])
            completed_lessons.append(current_lesson)  # Include current lesson
            completed_steps = [lesson for lesson in completed_lessons if is_actual_lesson(lesson)]
            total_steps = get_total_lesson_steps()

            # Calculate completion rate
            completion_rate = (len(completed_steps) / total_steps * 100) if total_steps > 0 else 0

            # Update progress metrics
            result = await asyncio.to_thread(
                db.users.update_one,
                {"user_id": user_id},
                {"$set": {
                    "current_lesson": lesson_key,
                    "last_active": current_date,
                    "progress_metrics.last_lesson_date": current_date,
                    "progress_metrics.completion_rate": round(completion_rate, 2),
                    "progress_metrics.total_responses": len(completed_steps)
                }}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Progress updated for user {user_id}: moved from {current_lesson} to {lesson_key}")
            else:
                logger.warning(f"No progress updated for user {user_id}")
            return success

        except Exception as e:
            logger.error(f"Error updating progress for user {user_id}: {e}", exc_info=True)
            return False

    @staticmethod
    async def update_learning_preferences(user_id: int, preferences: Dict[str, Any]) -> bool:
        """Update user's learning preferences."""
        try:
            result = db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "learning_preferences": preferences
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating preferences for user {user_id}: {e}")
            return False
        


class JournalManager:
    """Manages journal operations in MongoDB with improved data quality and validation"""
    
    @staticmethod
    async def save_journal_entry(user_id: str, lesson_key: str, response: str) -> bool:
        """
        Save a user's response to their journal with validation and error handling.
        
        Args:
            user_id: Telegram user ID
            lesson_key: Current lesson identifier
            response: User's response text
            
        Returns:
            bool: True if save successful, False otherwise
        """

        user_id = str(user_id)

        try:
            # Validate inputs
            if not response or not response.strip():
                logger.warning(f"Empty response from user {user_id}")
                return False
                
            if not lesson_key in lessons:
                logger.error(f"Invalid lesson key: {lesson_key}")
                return False
            
            # Prepare journal entry
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "lesson": lesson_key,
                "response": response.strip(),
                "response_length": len(response.strip()),
                "keywords_used": extract_keywords_from_response(response, lesson_key)
            }

            if not DataValidator.validate_journal_entry(entry):
                logger.error(f"Invalid journal entry for user {user_id}")
                return False
            
            # Update or create journal document using asyncio
            result = await asyncio.to_thread(
                db.journals.update_one,
                {"user_id": user_id},
                {
                    "$push": {"entries": entry},
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            
            if result.acknowledged:
                logger.info(f"Journal entry saved for user {user_id} in lesson {lesson_key}")
                return True
            
            logger.error(f"Failed to save journal entry for user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error saving journal entry for user {user_id}: {e}", exc_info=True)
            return False

    @staticmethod
    async def get_user_journal(user_id: int, limit: int = None) -> Optional[Dict[str, Any]]:
        """
        Get a user's journal entries with optional limit.
        
        Args:
            user_id: Telegram user ID
            limit: Optional maximum number of entries to return
            
        Returns:
            Dictionary containing journal entries or None if not found
        """
        try:
            # Base query
            query = {"user_id": user_id}
            
            # If limit specified, only get recent entries
            if limit:
                journal = db.journals.aggregate([
                    {"$match": query},
                    {"$unwind": "$entries"},
                    {"$sort": {"entries.timestamp": -1}},
                    {"$limit": limit},
                    {"$group": {
                        "_id": "$_id",
                        "user_id": {"$first": "$user_id"},
                        "entries": {"$push": "$entries"}
                    }}
                ]).next()
            else:
                journal = db.journals.find_one(query)
            
            if journal:
                journal.pop('_id', None)  # Remove MongoDB ID
                
            return journal
            
        except Exception as e:
            logger.error(f"Error retrieving journal for user {user_id}: {e}", exc_info=True)
            return None

    @staticmethod
    async def get_lesson_responses(lesson_key: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all user responses for a specific lesson.
        
        Args:
            lesson_key: Lesson identifier
            limit: Maximum number of responses to return
            
        Returns:
            List of responses with user info
        """
        try:
            responses = db.journals.aggregate([
                {"$unwind": "$entries"},
                {"$match": {"entries.lesson": lesson_key}},
                {"$limit": limit},
                {"$project": {
                    "user_id": 1,
                    "response": "$entries.response",
                    "timestamp": "$entries.timestamp",
                    "response_length": "$entries.response_length",
                    "keywords_used": "$entries.keywords_used"
                }}
            ])
            
            return list(responses)
            
        except Exception as e:
            logger.error(f"Error retrieving responses for lesson {lesson_key}: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_journal_statistics(user_id: int) -> Dict[str, Any]:
        """
        Get statistics about a user's journal entries.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary containing journal statistics
        """
        try:
            stats = db.journals.aggregate([
                {"$match": {"user_id": user_id}},
                {"$unwind": "$entries"},
                {"$group": {
                    "_id": "$user_id",
                    "total_entries": {"$sum": 1},
                    "avg_response_length": {"$avg": "$entries.response_length"},
                    "first_entry": {"$min": "$entries.timestamp"},
                    "last_entry": {"$max": "$entries.timestamp"}
                }}
            ]).next()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating journal stats for user {user_id}: {e}", exc_info=True)
            return {
                "total_entries": 0,
                "avg_response_length": 0,
                "first_entry": None,
                "last_entry": None
            }


class FeedbackManager:
    """Manages feedback operations in MongoDB"""

    @staticmethod
    async def save_feedback(user_id: str, feedback_text: str) -> bool:
        """Save user feedback with validation and error handling."""

        user_id = str(user_id)

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

            if not DataValidator.validate_feedback_data(feedback_data):
                logger.error(f"Invalid feedback data for user {user_id}")
                return False
            
            result = await asyncio.to_thread(
                db.feedback.insert_one,
                feedback_data
            )
            
            success = result.acknowledged
            if success:
                logger.info(f"Feedback saved for user {user_id} with ID {new_id}")
            else:
                logger.warning(f"Feedback not saved for user {user_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error saving feedback for user {user_id}: {e}", exc_info=True)
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


class FeedbackAnalyticsManager:
    """Manages feedback analytics and ratings in MongoDB."""

    @staticmethod
    async def save_feedback_analytics(user_id: int, lesson_id: str, feedback_results: dict) -> None:
        """Store feedback data for continuous improvement."""
        try:
            await asyncio.to_thread(
                db.feedback_analytics.update_one,
                {"user_id": user_id},
                {"$push": {
                    "lessons": {
                        "lesson_id": lesson_id,
                        "keywords_found": feedback_results.get("matches", []),
                        "feedback_given": feedback_results.get("feedback", []),
                        "quality_metrics": feedback_results.get("quality_metrics", {}),
                        "timestamp": datetime.now(timezone.utc)
                    }
                }},
                upsert=True
            )
            logger.info(f"Feedback analytics saved for user {user_id} and lesson {lesson_id}")
        except Exception as e:
            logger.error(f"Error saving feedback analytics for user {user_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def track_feedback_rating(user_id: int, rating: str) -> None:
        """Track feedback ratings for improvement."""
        try:
            db.feedback_ratings.update_one(
                {"user_id": user_id},
                {"$push": {"ratings": rating}},
                upsert=True
            )
            logger.info(f"Feedback rating tracked for user {user_id}: {rating}")
        
        except Exception as e:
            logger.error(f"Error tracking feedback rating for user {user_id}: {e}", exc_info=True)
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

            if not DataValidator.validate_task_data(task):
                logger.error(f"Invalid task data for lesson {lesson_key}")
                return None
            
            result = db.tasks.insert_one(task)
            if result.acknowledged:
                logger.info(f"Task #{next_id} created for lesson {lesson_key}")
                return task
            return None
            
        except OperationFailure as e:
            logger.error(f"Failed to create task: {e}")
            raise

    @staticmethod
    async def get_tasks_for_lesson(lesson_key: str) -> List[Dict[str, Any]]:
        """
        Get active tasks for a specific lesson.
        
        Args:
            lesson_key: Lesson identifier
            
        Returns:
            List of active tasks for the lesson
        """
        try:
            # Use asyncio to handle the database call
            tasks = await asyncio.to_thread(
                lambda: list(db.tasks.find({
                    "lesson": lesson_key,
                    "is_active": True
                }))
            )
            return [{k:v for k,v in task.items() if k != '_id'} for task in tasks]
        except Exception as e:
            logger.error(f"Failed to get tasks for lesson {lesson_key}: {e}")
            return []

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


class AnalyticsManager:
    """Manages learning analytics and user progress tracking in MongoDB."""

    @staticmethod
    async def calculate_user_metrics(user_id: str) -> Dict[str, Any]:
        """Calculate comprehensive metrics for a single user."""

        user_id = str(user_id)

        try:
            # Get user data and journal entries using asyncio
            user_data = await asyncio.to_thread(
                db.users.find_one,
                {"user_id": user_id}
            )
            journal = await asyncio.to_thread(
                db.journals.find_one,
                {"user_id": user_id}
            )
            
            if not user_data or not journal or not journal.get('entries'):
                logger.warning(f"No data found for user {user_id}")
                return {}
            
            # Get all entries and sort by timestamp
            entries = sorted(journal['entries'], 
                        key=lambda x: x['timestamp'])
            
            # Calculate basic metrics with safe access
            total_responses = len(entries)
            avg_response_length = 0
            if total_responses > 0:
                # Safely get response lengths, defaulting to 0 if not present
                response_lengths = [e.get('response_length', len(e.get('response', ''))) for e in entries]
                avg_response_length = sum(response_lengths) / total_responses
            
            # Calculate time-based metrics
            learning_duration = 0
            avg_days_between_lessons = 0
            if len(entries) >= 2:
                start_time = datetime.fromisoformat(entries[0]['timestamp'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(entries[-1]['timestamp'].replace('Z', '+00:00'))
                if not start_time.tzinfo:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                if not end_time.tzinfo:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                learning_duration = (end_time - start_time).days
                avg_days_between_lessons = learning_duration / (len(entries) - 1) if len(entries) > 1 else 0
            
            # Safely get progress metrics with defaults
            progress_metrics = user_data.get('progress_metrics', {})
            completion_rate = progress_metrics.get('completion_rate', 0)
            
            # Calculate engagement score (0-100)
            engagement_factors = {
                'response_length': min(avg_response_length / 100, 1) * 30,  # 30% weight
                'completion_rate': completion_rate,  # 40% weight
                'consistency': min(7 / (avg_days_between_lessons if avg_days_between_lessons > 0 else 7), 1) * 30  # 30% weight
            }
            engagement_score = sum(engagement_factors.values())
            
            # Compile metrics with safe defaults
            return {
                "total_responses": total_responses,
                "average_response_length": round(avg_response_length, 2),
                "completed_lessons": len(user_data.get('completed_lessons', [])),
                "completion_rate": round(completion_rate, 2),
                "learning_duration_days": learning_duration,
                "avg_days_between_lessons": round(avg_days_between_lessons, 2),
                "engagement_score": round(engagement_score, 2),
                "last_active": user_data.get('last_active', 'Never'),
                "current_lesson": user_data.get('current_lesson', 'None')
            }
                
        except Exception as e:
            logger.error(f"Error calculating metrics for user {user_id}: {e}", exc_info=True)
            return {}

    @staticmethod
    def calculate_cohort_metrics(start_date: Optional[str] = None, 
                               end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate metrics across all users within a date range.
        
        Args:
            start_date: Optional ISO format start date
            end_date: Optional ISO format end date
            
        Returns:
            Dictionary containing cohort metrics
        """
        try:
            # Build date range query
            query = {}
            if start_date or end_date:
                query['joined_date'] = {}
                if start_date:
                    query['joined_date']['$gte'] = start_date
                if end_date:
                    query['joined_date']['$lte'] = end_date
            
            # Get all users in date range
            users = list(db.users.find(query))
            
            if not users:
                return {}
            
            # Calculate aggregate metrics
            total_users = len(users)
            completion_rates = [u['progress_metrics']['completion_rate'] for u in users]
            avg_completion_rate = sum(completion_rates) / total_users if total_users > 0 else 0
            
            # Count users at each lesson
            lesson_distribution = {}
            for user in users:
                current_lesson = user.get('current_lesson')
                if current_lesson:
                    lesson_distribution[current_lesson] = lesson_distribution.get(current_lesson, 0) + 1
            
            # Calculate retention metrics
            active_last_day = sum(1 for u in users if 
                                datetime.fromisoformat(u['last_active'].replace('Z', '+00:00')) >
                                datetime.now(timezone.utc) - timedelta(days=1))
            
            active_last_week = sum(1 for u in users if 
                                 datetime.fromisoformat(u['last_active'].replace('Z', '+00:00')) >
                                 datetime.now(timezone.utc) - timedelta(days=7))
            
            return {
                "total_users": total_users,
                "average_completion_rate": round(avg_completion_rate, 2),
                "lesson_distribution": lesson_distribution,
                "active_users": {
                    "last_24h": active_last_day,
                    "last_7d": active_last_week
                },
                "retention_rates": {
                    "daily": round((active_last_day / total_users * 100), 2) if total_users > 0 else 0,
                    "weekly": round((active_last_week / total_users * 100), 2) if total_users > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating cohort metrics: {e}", exc_info=True)
            return {}

    @staticmethod
    def get_lesson_analytics(lesson_key: str) -> Dict[str, Any]:
        """
        Get analytics for a specific lesson.
        
        Args:
            lesson_key: The lesson identifier
            
        Returns:
            Dictionary containing lesson analytics
        """
        try:
            # Get all responses for this lesson
            responses = list(db.journals.aggregate([
                {"$unwind": "$entries"},
                {"$match": {"entries.lesson": lesson_key}},
                {"$project": {
                    "response_length": "$entries.response_length",
                    "keywords_used": "$entries.keywords_used",
                    "timestamp": "$entries.timestamp"
                }}
            ]))
            
            if not responses:
                return {}
            
            # Calculate response metrics
            total_responses = len(responses)
            avg_response_length = sum(r['response_length'] for r in responses) / total_responses if total_responses > 0 else 0
            
            # Analyze keywords
            all_keywords = [kw for r in responses for kw in r.get('keywords_used', [])]
            keyword_frequency = {}
            if all_keywords:
                keyword_frequency = {kw: all_keywords.count(kw) for kw in set(all_keywords)}
            
            # Calculate completion time distribution
            completion_times = []
            users_completed = set()
            
            user_responses = db.journals.aggregate([
                {"$unwind": "$entries"},
                {"$match": {"entries.lesson": lesson_key}},
                {"$group": {
                    "_id": "$user_id",
                    "completed_at": {"$min": "$entries.timestamp"}
                }}
            ])
            
            for response in user_responses:
                users_completed.add(response['_id'])
                completion_times.append(response['completed_at'])
            
            return {
                "total_responses": total_responses,
                "average_response_length": round(avg_response_length, 2),
                "unique_completions": len(users_completed),
                "keyword_frequency": keyword_frequency,
                "responses_per_day": round(total_responses / (7 if total_responses > 7 else 1), 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating lesson analytics for {lesson_key}: {e}", exc_info=True)
            return {}
        
db = init_mongodb()