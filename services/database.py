from motor.motor_asyncio import AsyncIOMotorClient
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
from collections import Counter
from services.feedback_templates import FEEDBACK_TEMPLATES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__) # Get logger instance


lessons = content_loader.load_content('lessons')


# Create directories for storage
async def init_mongodb(max_retries=3, retry_delay=2):
    """Initialize MongoDB connection with retry mechanism and health check."""
    global db  # Modify the global db variable
    
    for attempt in range(max_retries):
        try:
            MONGODB_URI = Config.MONGODB_URI
            if not MONGODB_URI:
                raise ValueError("MONGODB_URI environment variable not set!")

            client = AsyncIOMotorClient(
                MONGODB_URI,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=5000
            )

            # Test connection
            await client.admin.command('ping')

            # Get database
            db = client["gclearnbot"]

            # Ensure required collections and indices exist
            await asyncio.gather(
                db.users.create_index("email", unique=True),
                db.journals.create_index("user_id"),
                _ensure_collection_with_index(db, "user_skills", "user_id"),
                _ensure_collection_with_index(db, "learning_insights", "user_id"),
                db.feedback_analytics.create_index("user_id"),
                db.feedback_analytics.create_index([("user_id", 1), ("entries.lesson_id", 1)])
            )

            # Database health check to ensure collections are accessible
            try:
                await asyncio.gather(
                    db.users.find_one(),
                    db.journals.find_one(),
                    db.learning_insights.find_one()
                )
                logger.info("Database health check passed.")
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
                raise

            logger.info("MongoDB connection successful")
            return db

        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"MongoDB connection error after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)

async def _ensure_collection_with_index(db, collection_name, index_field):
    """Ensure a collection exists and create an index if needed."""
    collections = await db.list_collection_names()
    if collection_name not in collections:
        await db.create_collection(collection_name)
        await db[collection_name].create_index(index_field, unique=True)
        logger.info(f"Created {collection_name} collection with index on {index_field}")


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
    async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by Telegram ID with improved logging"""
        try:
            user = await db.users.find_one({"telegram_id": telegram_id, "platforms": "telegram"})
            if user:
                user.pop('_id', None)
                logger.info(f"Found user for Telegram ID {telegram_id}")
            else:
                logger.info(f"No user found for Telegram ID {telegram_id}")
            return user
        except Exception as e:
            logger.error(f"Error getting user by telegram_id: {e}")
            return None

    @staticmethod
    async def link_telegram_account(email: str, telegram_id: int, telegram_data: Dict[str, Any]) -> bool:
        """Link Telegram account to existing user with better error handling"""
        masked_email = email[:3] + "..." + email.split("@")[-1]
        try:
            result = await db.users.update_one(
                {"email": email},
                {
                    "$set": {
                        "telegram_id": telegram_id,
                        "username": telegram_data.get("username"),
                        "first_name": telegram_data.get("first_name", ""),
                        "last_name": telegram_data.get("last_name", ""),
                        "last_active": datetime.now(timezone.utc).isoformat()
                    },
                    "$addToSet": {
                        "platforms": "telegram"
                    }
                }
            )
            success = result.modified_count > 0
            if success:
                logger.info(f"Successfully linked Telegram account {telegram_id} to email {masked_email}")
            else:
                logger.error(f"Failed to link Telegram account {telegram_id} to email {masked_email}")
            return success

        except Exception as e:
            logger.error(f"Error linking Telegram account: {e}")
            return False

    @staticmethod
    async def save_user_info(user, platform: str = 'telegram', email: str = None) -> Dict[str, Any]:
        """Save comprehensive user information when they start using the bot or link their email."""
        try:
            # Support both object and dictionary inputs
            if isinstance(user, dict):
                user_id = str(user.get("user_id"))
                username = user.get("username", "")
                first_name = user.get("first_name", "")
                last_name = user.get("last_name", "")
                language_code = user.get("language_code", "en")
                telegram_id = user.get("telegram_id")  # May already be present in dict
            else:
                user_id = str(user.id)
                username = user.username if platform == 'telegram' else user.get('name', '')
                first_name = user.first_name if platform == 'telegram' else user.get('real_name', '')
                last_name = user.last_name or ""
                language_code = user.language_code or "en"
                telegram_id = user.id if platform == 'telegram' else None

            # Build user_data including telegram_id if available
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
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
                    "preferred_language": language_code,
                    "notification_enabled": True
                }
            }
            if telegram_id:
                user_data["telegram_id"] = telegram_id

            # If an email is provided, add it along with chat_id
            update_fields = {"$set": user_data}
            if email:
                update_fields["$set"]["email"] = email

                if isinstance(user, dict) and "chat_id" in user:
                    update_fields["$set"]["chat_id"] = user["chat_id"]
                elif platform == 'telegram':
                    update_fields["$set"]["chat_id"] = user_id

            if not DataValidator.validate_user_data(user_data):
                logger.error(f"Invalid user data for user {user_id}")
                return None

            result = await db.users.update_one(
                {"user_id": user_id, "platform": platform},
                update_fields,
                upsert=True
            )

            if not result.acknowledged:
                raise OperationFailure("Failed to save user data")

            logger.info(f"User data saved/updated for user {user_id}")
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

            user_data = await db.users.find_one(
                {"user_id": user_id, "platform": platform}
            )
            
            if user_data:
                # Ensure `current_lesson` exists, default to lesson_1
                if "current_lesson" not in user_data:
                    user_data["current_lesson"] = "lesson_1"
                    await db.users.update_one(
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
            user_data = await db.users.find_one(
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

            result = await db.users.update_one(
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
        """
        try:
            # Log the start of progress update
            logger.info(f"Starting progress update for user {user_id} to lesson {lesson_key}")

            if lesson_key not in lessons:
                logger.error(f"Invalid lesson key: {lesson_key}")
                return False

            # Get current user data - properly await the async operation
            user_data = await db.users.find_one({"user_id": user_id})

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

            # Update completed lessons - properly await the async operation
            await db.users.update_one(
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

            # Update progress metrics - properly await the async operation
            result = await db.users.update_one(
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
            result = await db.users.update_one(
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
    async def save_journal_entry(user_id: str, lesson_key: str, response: str, keywords: Optional[Dict[str, List[str]]] = None) -> bool:
        """
        Save a user's response to their journal with validation and error handling.
        
        Args:
            user_id: The user's ID
            lesson_key: The lesson identifier
            response: The user's response text
            keywords: Optional dictionary of keyword types and their matched keywords
        """
        user_id = str(user_id)

        try:
            # Validate inputs
            if not response or not response.strip():
                logger.warning(f"Empty response from user {user_id}")
                return False

            if lesson_key not in lessons:
                logger.error(f"Invalid lesson key: {lesson_key}")
                return False

            # Prepare journal entry
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "lesson": lesson_key,
                "response": response.strip(),
                "response_length": len(response.strip()),
                "keywords_used": extract_keywords_from_response(response, lesson_key),
                # Add new keyword tracking, with a default empty dict if None
                "enhanced_keywords": keywords or {}
            }

            if not DataValidator.validate_journal_entry(entry):
                logger.error(f"Invalid journal entry for user {user_id}")
                return False

            # Update or create journal document
            result = await db.journals.update_one(
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
    async def get_user_journal(user_id: int, page: int = 1, per_page: int = 10) -> Optional[Dict[str, Any]]:
        """Get a user's journal entries with pagination."""
        try:
            # Calculate skip value
            skip = (page - 1) * per_page

            pipeline = [
                {"$match": {"user_id": user_id}},
                # First get total count
                {
                    "$facet": {
                        "metadata": [{"$count": "total"}],
                        "entries": [
                            {"$unwind": "$entries"},
                            {"$sort": {"entries.timestamp": -1}},
                            {"$skip": skip},
                            {"$limit": per_page},
                            {
                                "$group": {
                                    "_id": "$_id",
                                    "entries": {"$push": "$entries"}
                                }
                            }
                        ]
                    }
                }
            ]

            result = await db.journals.aggregate(pipeline).to_list(None)
            
            if not result or not result[0].get('entries'):
                return None
                
            # Get total count and entries
            total = result[0]['metadata'][0]['total'] if result[0]['metadata'] else 0
            entries = result[0]['entries'][0]['entries'] if result[0]['entries'] else []
            
            return {
                "entries": entries,
                "total": total,
                "current_page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }

        except Exception as e:
            logger.error(f"Error retrieving journal for user {user_id}: {e}")
            return None

    @staticmethod
    async def get_lesson_responses(lesson_key: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all user responses for a specific lesson.
        """
        try:
            pipeline = [
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
            ]
            cursor = db.journals.aggregate(pipeline)
            responses = await cursor.to_list(length=None)
            return responses

        except Exception as e:
            logger.error(f"Error retrieving responses for lesson {lesson_key}: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_journal_statistics(user_id: int) -> Dict[str, Any]:
        """
        Get statistics about a user's journal entries.
        """
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$unwind": "$entries"},
                {"$group": {
                    "_id": "$user_id",
                    "total_entries": {"$sum": 1},
                    "avg_response_length": {"$avg": "$entries.response_length"},
                    "first_entry": {"$min": "$entries.timestamp"},
                    "last_entry": {"$max": "$entries.timestamp"}
                }}
            ]
            cursor = db.journals.aggregate(pipeline)
            stats_list = await cursor.to_list(length=1)
            stats = stats_list[0] if stats_list else {
                "total_entries": 0,
                "avg_response_length": 0,
                "first_entry": None,
                "last_entry": None
            }
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
            current_max_id = await db.feedback.find_one(sort=[("id", -1)]) or {}
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
            
            result = await db.feedback.insert_one(feedback_data)
            
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
        """
        try:
            cursor = db.feedback.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
            feedback_list = await cursor.to_list(length=limit)
            for doc in feedback_list:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
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
        """
        try:
            update = {"$set": {"processed": True, "processed_at": datetime.now(timezone.utc).isoformat()}}
            if category:
                update["$set"]["category"] = category

            result = await db.feedback.update_one({"id": feedback_id}, update)
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
            # Keep existing functionality
            await db.feedback_analytics.update_one(
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
            
            # Add analysis of strengths/weaknesses
            entry_data = feedback_results.get("quality_metrics", {})
            await db.feedback_analytics.update_one(
                {"user_id": user_id},
                {"$push": {
                    "entries": {
                        "timestamp": datetime.now(timezone.utc),
                        "lesson_id": lesson_id,
                        "strengths": entry_data.get("strengths", []),
                        "weaknesses": entry_data.get("weaknesses", []),
                    }
                }}
            )
            
            logger.info(f"Feedback analytics saved for user {user_id} and lesson {lesson_id}")
        except Exception as e:
            logger.error(f"Error saving feedback analytics: {e}", exc_info=True)
            raise

    @staticmethod
    async def get_personalization_data(user_id: int) -> dict:
        """Get personalized data for feedback templates."""
        try:
            analytics = await db.feedback_analytics.find_one({"user_id": user_id})
            if not analytics:
                return {}
                
            entries = analytics.get("entries", [])
            if not entries:
                return {}
            
            # Get recurring patterns
            strengths = Counter()
            weaknesses = Counter()
            
            for entry in entries[-5:]:
                strengths.update(entry.get("strengths", []))
                weaknesses.update(entry.get("weaknesses", []))
            
            return {
                "top_strengths": [s for s, _ in strengths.most_common(2)],
                "top_weaknesses": [w for w, _ in weaknesses.most_common(2)],
                "response_count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error getting personalization data: {e}")
            return {}

    @staticmethod
    async def update_recurring_patterns(user_id: int) -> None:
        """Update recurring patterns in user's feedback analytics."""
        try:
            analytics = await db.feedback_analytics.find_one({"user_id": user_id})
            if not analytics or len(analytics.get("entries", [])) < 3:
                return
                
            entries = analytics["entries"][-5:]
            patterns = {
                "consistent_strengths": [s for s, _ in Counter(
                    s for e in entries for s in e.get("strengths", [])
                ).most_common(3)],
                "consistent_weaknesses": [w for w, _ in Counter(
                    w for e in entries for w in e.get("weaknesses", [])
                ).most_common(3)]
            }
            
            await db.feedback_analytics.update_one(
                {"user_id": user_id},
                {"$set": {"recurring_patterns": patterns}}
            )
            
        except Exception as e:
            logger.error(f"Error updating recurring patterns: {e}")

    @staticmethod
    async def track_feedback_rating(user_id: int, rating: str) -> None:
        """Track feedback ratings for improvement."""
        try:
            await db.feedback_ratings.update_one(
                {"user_id": user_id},
                {"$push": {"ratings": rating}},
                upsert=True
            )
            logger.info(f"Feedback rating tracked for user {user_id}: {rating}")

        except Exception as e:
            logger.error(f"Error tracking feedback rating for user {user_id}: {e}", exc_info=True)
            raise



class AnalyticsManager:
    """Manages learning analytics and user progress tracking in MongoDB."""

    @staticmethod
    async def calculate_user_metrics(user_id: str) -> Dict[str, Any]:
        """Calculate comprehensive metrics for a single user."""

        user_id = str(user_id)

        try:
            # Get user data and journal entries using asyncio
            user_data = await db.users.find_one({"user_id": user_id})
            journal = await db.journals.find_one({"user_id": user_id})
            
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
    async def calculate_cohort_metrics(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate metrics across all users within a date range.
        """
        try:
            query = {}
            if start_date or end_date:
                query['joined_date'] = {}
                if start_date:
                    query['joined_date']['$gte'] = start_date
                if end_date:
                    query['joined_date']['$lte'] = end_date

            cursor = db.users.find(query)
            users = await cursor.to_list(length=None)
            if not users:
                return {}

            total_users = len(users)
            completion_rates = [u['progress_metrics']['completion_rate'] for u in users]
            avg_completion_rate = sum(completion_rates) / total_users if total_users > 0 else 0

            lesson_distribution = {}
            for user in users:
                current_lesson = user.get('current_lesson')
                if current_lesson:
                    lesson_distribution[current_lesson] = lesson_distribution.get(current_lesson, 0) + 1

            active_last_day = sum(
                1 for u in users if datetime.fromisoformat(u['last_active'].replace('Z', '+00:00')) >
                datetime.now(timezone.utc) - timedelta(days=1)
            )
            active_last_week = sum(
                1 for u in users if datetime.fromisoformat(u['last_active'].replace('Z', '+00:00')) >
                datetime.now(timezone.utc) - timedelta(days=7)
            )

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
    async def get_lesson_analytics(lesson_key: str) -> Dict[str, Any]:
        """
        Get analytics for a specific lesson.
        """
        try:
            pipeline = [
                {"$unwind": "$entries"},
                {"$match": {"entries.lesson": lesson_key}},
                {"$project": {
                    "response_length": "$entries.response_length",
                    "keywords_used": "$entries.keywords_used",
                    "timestamp": "$entries.timestamp"
                }}
            ]
            cursor = db.journals.aggregate(pipeline)
            responses = await cursor.to_list(length=None)
            if not responses:
                return {}

            total_responses = len(responses)
            avg_response_length = sum(r['response_length'] for r in responses) / total_responses if total_responses > 0 else 0

            all_keywords = [kw for r in responses for kw in r.get('keywords_used', [])]
            keyword_frequency = {kw: all_keywords.count(kw) for kw in set(all_keywords)} if all_keywords else {}

            user_responses_cursor = db.journals.aggregate([
                {"$unwind": "$entries"},
                {"$match": {"entries.lesson": lesson_key}},
                {"$group": {
                    "_id": "$user_id",
                    "completed_at": {"$min": "$entries.timestamp"}
                }}
            ])
            user_responses = await user_responses_cursor.to_list(length=None)
            users_completed = {response['_id'] for response in user_responses}

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
        
db = None

async def get_db():
    """Get database instance, initializing if necessary"""
    global db
    try:
        if db is None:
            db = await init_mongodb()
        return db
    except Exception as e:
        logger.error(f"Failed to get database connection: {e}")
        raise