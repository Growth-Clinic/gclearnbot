from quart import Quart, request, jsonify, ResponseReturnValue, send_from_directory
from services.database import get_db, AnalyticsManager, UserManager, JournalManager, FeedbackAnalyticsManager
from services.lesson_manager import LessonService
from services.progress_tracker import ProgressTracker
from services.learning_insights import LearningInsightsManager
from services.content_loader import content_loader
from services.utils import verify_password
from services.feedback_templates import FEEDBACK_TEMPLATES
from config.settings import Config
from datetime import datetime, timezone
import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application
import json
import bcrypt
from flask_jwt_extended import decode_token, verify_jwt_in_request, JWTManager, create_access_token, jwt_required, get_jwt_identity
import jwt
from werkzeug.security import generate_password_hash
from functools import wraps
from uuid import uuid4


logger = logging.getLogger(__name__)

app = Quart(__name__)
db = None
JWT_SECRET_KEY = Config.JWT_SECRET_KEY
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")  # Use Render environment variable
# jwt = JWTManager(app)  # Initialize JWT authentication

@app.before_serving
async def before_serving():
    """Initialize database connection before serving"""
    global db
    db = await get_db()
    logger.info("Database initialized")

@app.before_request
async def ensure_context():
    """Ensure app context is available for JWT operations"""
    if not app.app_context:
        await app.app_context().__aenter__()

def async_jwt_required():
    def wrapper(fn):
        @wraps(fn)
        async def decorator(*args, **kwargs):
            try:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("Bearer "):
                    return jsonify({"status": "error", "message": "Missing token"}), 401
                
                token = auth_header.split(" ")[1]
                try:
                    # Use PyJWT directly
                    decoded = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
                    request.user_email = decoded.get('sub')
                    if not request.user_email:
                        return jsonify({"status": "error", "message": "Invalid token"}), 401
                    
                    return await fn(*args, **kwargs)
                except jwt.InvalidTokenError:
                    return jsonify({"status": "error", "message": "Invalid token"}), 401
                    
            except Exception as e:
                logger.error(f"Auth error: {e}")
                return jsonify({"status": "error", "message": "Authentication error"}), 500
                
        return decorator
    return wrapper

def setup_routes(app: Quart, application: Application) -> None:

    """Set up API routes for web access"""

    lesson_service = LessonService(user_manager=UserManager())
    progress_tracker = ProgressTracker()

    @app.route('/register', methods=['POST'])
    async def register():
        """Register a new user and return a JWT token"""
        try:
            data = await request.get_json()
            logger.info(f"Received registration data: {data}")

            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return jsonify({"status": "error", "message": "Email and password required"}), 400

            # Initialize database connection
            db = await get_db()

            # Check if user already exists - properly awaiting the result
            existing_user = await db.users.find_one({"email": email})
            
            # If user exists but doesn't have a password (maybe from Telegram), update it
            if existing_user:
                if not existing_user.get('password'):
                    result = await db.users.update_one(
                        {"email": email},
                        {"$set": {"password": generate_password_hash(password)}}
                    )
                    if result.modified_count > 0:
                        token = jwt.encode(
                            {"sub": email},
                            JWT_SECRET_KEY,
                            algorithm="HS256"
                        )
                        return jsonify({
                            "status": "success",
                            "token": token
                        }), 200
                else:
                    return jsonify({"status": "error", "message": "Email already registered"}), 409

            # Generate a UUID for user_id
            user_id = str(uuid4())
            username = email.split('@')[0]

            # Create user data structure
            user_data = {
                "user_id": user_id,
                "email": email,
                "password": generate_password_hash(password),
                "platform": "web",
                "platforms": ["web"],
                "username": username,
                "first_name": "",
                "language_code": "en",
                "joined_date": datetime.now(timezone.utc).isoformat(),
                "current_lesson": "lesson_1",
                "completed_lessons": [],
                "last_active": datetime.now(timezone.utc).isoformat(),
                "learning_preferences": {
                    "preferred_language": "en",
                    "notification_enabled": True
                },
                "progress_metrics": {
                    "total_responses": 0,
                    "average_response_length": 0,
                    "completion_rate": 0,
                    "last_lesson_date": None
                }
            }

            # Save user to database - properly awaiting the result
            result = await db.users.insert_one(user_data)

            if not result.acknowledged:
                logger.error("Failed to save user to database")
                return jsonify({"status": "error", "message": "Database error"}), 500

            # Generate JWT token
            token = jwt.encode(
                {"sub": email},
                JWT_SECRET_KEY,
                algorithm="HS256"
            )

            return jsonify({
                "status": "success",
                "token": token
            }), 201

        except Exception as e:
            logger.error(f"Registration error: {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Server error"}), 500

    
    @app.route('/login', methods=['POST'])
    async def login():
        """Authenticate user and return JWT"""
        try:
            data = await request.get_json()
            logger.info(f"Login request received: {data}")

            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return jsonify({"status": "error", "message": "Missing email or password"}), 400

            # Get database instance
            db = await get_db()
            
            # Execute database query and await result
            result = await db.users.find_one({"email": email})
            
            if not result:
                logger.info(f"User not found: {email}")
                return jsonify({"status": "error", "message": "User not found"}), 404

            if not verify_password(password, result["password"]):
                logger.info(f"Invalid password for user: {email}")
                return jsonify({"status": "error", "message": "Invalid credentials"}), 401

            # Use PyJWT directly for token generation
            import jwt as pyjwt
            token = pyjwt.encode(
                {"sub": email}, 
                JWT_SECRET_KEY, 
                algorithm="HS256"
            )

            logger.info(f"Login successful for user: {email}")
            return jsonify({
                "status": "success", 
                "token": token
            }), 200

        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Server error"}), 500
        

    @app.route('/protected', methods=['GET'])
    @jwt_required()
    async def protected():
        """Example protected route"""
        current_user = get_jwt_identity()
        return jsonify(logged_in_as=current_user), 200
    
    # ✅ Serve static files from the web directory
    @app.route('/web/<path:filename>')
    async def serve_static(filename):
        try:
            # Get absolute path to web directory
            web_dir = os.path.join(os.getcwd(), "web")
            
            # Check if file exists
            if not os.path.exists(os.path.join(web_dir, filename)):
                logger.error(f"File not found: {filename}")
                return {"error": "File not found"}, 404
                
            return await send_from_directory(web_dir, filename)
        except Exception as e:
            logger.error(f"Error serving static file {filename}: {e}")
            return {"error": "Internal server error"}, 500
    
    @app.route('/lessons', methods=['GET'])
    async def list_lessons():
        """Return a list of all available lessons"""
        try:
            lessons = content_loader.load_content('lessons')  # Load from JSON
            lesson_list = [{"lesson_id": key, "title": value.get("title", f"Lesson {key}")} for key, value in lessons.items()]
            
            return jsonify({"status": "success", "lessons": lesson_list}), 200

        except Exception as e:
            logger.error(f"Error listing lessons: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route('/lessons/<lesson_id>', methods=['GET'])
    async def get_lesson(lesson_id):
        """Fetch a lesson with progress details (similar to bot)."""
        try:
            lessons = content_loader.load_content('lessons')
            lesson = lessons.get(lesson_id)

            if not lesson:
                return jsonify({"status": "error", "message": "Lesson not found"}), 404

            # Extract progress details
            parts = lesson_id.split('_')
            lesson_num = parts[1] if len(parts) > 1 else '1'
            step_num = parts[3] if len(parts) > 3 and 'step' in parts else None

            # Format progress header
            header = f"📚 Lesson {lesson_num} of 6"
            if step_num:
                header += f"\nStep {step_num}"

            return jsonify({
                "status": "success",
                "lesson": {
                    "lesson_id": lesson_id,
                    "title": lesson.get("title", f"Lesson {lesson_num}"),
                    "text": f"{header}\n\n{lesson['text']}",
                    "next": lesson.get("next", None)  # Next lesson ID
                }
            }), 200

        except Exception as e:
            logger.error(f"Error fetching lesson {lesson_id}: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route('/lessons/<lesson_id>/response', methods=['POST'])
    @async_jwt_required()
    async def submit_lesson_response(lesson_id):
        """Submit a user response for a lesson"""
        try:
            user_email = request.user_email
            
            # Get database instance
            db = await get_db()
            
            # Get user data
            user = await db.users.find_one({"email": user_email})
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            user_id = user.get('user_id')
            data = await request.get_json()
            response_text = data.get("response")
            keywords_found = data.get("keywords_found", {})

            if not user_id or not response_text:
                return jsonify({"status": "error", "message": "Missing user_id or response"}), 400

            # Save journal entry with enhanced keyword tracking
            await JournalManager.save_journal_entry(user_id, lesson_id, response_text, {
                "standard_keywords": keywords_found.get('standard', []),
                "stemmed_keywords": keywords_found.get('stemmed', []),
                "synonym_keywords": keywords_found.get('synonyms', [])
            })

            # Update progress
            await UserManager.update_user_progress(user_id, lesson_id)

            return jsonify({
                "status": "success", 
                "message": "Response saved",
                "keywords": keywords_found
            }), 200

        except Exception as e:
            logger.error(f"Error submitting response for lesson {lesson_id}: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route('/progress', methods=['GET'])
    @async_jwt_required()
    async def get_progress():
        """Fetch user progress"""
        try:
            user_email = request.user_email
            
            # Get database instance
            db = await get_db()
            
            # Get user data
            user_data = await db.users.find_one({"email": user_email})
            if not user_data:
                return jsonify({"status": "error", "message": "User not found"}), 404

            completed_lessons = user_data.get('completed_lessons', [])
            return jsonify({
                "status": "success",
                "progress": {
                    "completed_lessons": completed_lessons
                }
            }), 200

        except Exception as e:
            logger.error(f"Error fetching progress: {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route('/progress/complete/<user_id>', methods=['GET'])
    async def get_complete_progress(user_id):
        """Fetch complete progress report"""
        try:
            progress_report = await progress_tracker.get_complete_progress(user_id, platform="web")
            return jsonify({"status": "success", "progress": progress_report}), 200
        except Exception as e:
            logger.error(f"Error fetching complete progress for user {user_id}: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route('/journal')
    @async_jwt_required()
    async def get_journal():
        """Fetch user's journal entries with pagination"""
        try:
            user_email = request.user_email
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            # Get database instance
            db = await get_db()
                
            user = await db.users.find_one({"email": user_email})
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404

            journal = await JournalManager.get_user_journal(user['user_id'], page, per_page)
            
            if journal:
                return jsonify({
                    "status": "success",
                    "journal": journal['entries'],
                    "pagination": {
                        "current_page": journal['current_page'],
                        "per_page": journal['per_page'],
                        "total_pages": journal['total_pages'],
                        "total_entries": journal['total']
                    }
                }), 200
                
            return jsonify({"status": "success", "journal": [], "pagination": {
                "current_page": 1,
                "per_page": per_page,
                "total_pages": 0,
                "total_entries": 0
            }}), 200

        except Exception as e:
            logger.error(f"Error fetching journal: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

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
            
            # Check content type
            if request.headers.get('content-type') != 'application/json':
                logger.error(f"Invalid content type: {request.headers.get('content-type')}")
                return jsonify({"status": "error", "message": "Invalid content type"}), 400
                
            # Get raw data first
            raw_data = await request.get_data()
            if not raw_data:
                logger.error("Empty request body")
                return jsonify({"status": "error", "message": "Empty request body"}), 400
                
            try:
                json_data = await request.get_json(force=True)
                if not json_data:
                    logger.error("Empty JSON data")
                    return jsonify({"status": "error", "message": "Empty JSON data"}), 400
                    
                logger.info(f"Received webhook data: {json_data}")
                
                update = Update.de_json(json_data, application.bot)
                await application.process_update(update)
                return jsonify({"status": "ok"})
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return jsonify({"status": "error", "message": "Invalid JSON format"}), 400
                
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500



    @app.route('/')
    async def serve_frontend():
        """Serve index.html when users visit the base URL."""
        return await send_from_directory(os.path.join(os.getcwd(), "web"), "index.html")

    @app.route('/status')
    def bot_status():
        """Check if the bot is running."""
        return "Bot is running!"

    # Flask routes for viewing journals
    @app.route('/journals/<user_id>')
    async def view_journal(user_id):
        """Admin route to view specific journal"""
        try:

            # Get database instance
            db = await get_db()

            # Add auth check
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"status": "error", "message": "Missing or invalid token"}), 401

            token = auth_header.split(" ")[1]
            
            with app.app_context():
                decoded = decode_token(token)
                user_email = decoded['sub']
                
                # Verify admin status (you'll need to add admin field to user model)
                admin_user = await db.users.find_one({"email": user_email})
                if not admin_user or not admin_user.get('is_admin'):
                    return jsonify({"status": "error", "message": "Unauthorized"}), 403

            # Convert user_id to proper format
            try:
                user_id = str(user_id)
            except ValueError:
                return jsonify({"error": "Invalid user ID"}), 400
                
            journal = await db.journals.find_one({"user_id": user_id})
            if journal:
                journal.pop('_id', None)
                return jsonify(journal)
            return jsonify({"error": "Journal not found"}), 404
        except Exception as e:
            logger.error(f"Error fetching journal: {e}")
            return jsonify({"error": "Server error"}), 500

    @app.route('/journals')
    async def list_journals():
        """Admin route to list all journals"""
        try:

            # Get database instance
            db = await get_db()
            
            # Add same auth check as above
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"status": "error", "message": "Missing or invalid token"}), 401

            token = auth_header.split(" ")[1]
            
            with app.app_context():
                decoded = decode_token(token)
                user_email = decoded['sub']
                
                admin_user = await db.users.find_one({"email": user_email})
                if not admin_user or not admin_user.get('is_admin'):
                    return jsonify({"status": "error", "message": "Unauthorized"}), 403

            # Use async operation
            journals = await db.journals.find().to_list(length=None)
            
            # Remove MongoDB _id from each journal
            for journal in journals:
                journal.pop('_id', None)
                
            return jsonify({"status": "success", "journals": journals})
        except Exception as e:
            logger.error(f"Error listing journals: {e}")
            return jsonify({"error": "Server error"}), 500

    @app.route('/health')
    async def health_check():
        """Health check endpoint"""
        try:
            # Test DB connection
            await db.users.find_one
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
            await db.users.find_one
            logger.debug("Warm-up successful")
        except Exception as e:
            logger.error(f"Warm-up failed: {e}")


    @app.route('/analytics')
    async def get_analytics():
        """Analytics endpoint for dashboard"""
        try:
            # Get analytics data
            cohort_metrics = AnalyticsManager.calculate_cohort_metrics()
            
            # Return formatted response
            return jsonify({
                "status": "success",
                "data": {
                    "user_metrics": {
                        "total_users": cohort_metrics.get('total_users', 0),
                        "active_users": cohort_metrics.get('active_users', {}),
                        "retention_rates": cohort_metrics.get('retention_rates', {})
                    },
                    "learning_metrics": {
                        "average_completion_rate": cohort_metrics.get('average_completion_rate', 0),
                        "lesson_distribution": cohort_metrics.get('lesson_distribution', {})
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"Error generating analytics API response: {e}")
            return jsonify({
                "status": "error",
                "message": "Error generating analytics"
            }), 500
        
    @app.route('/admin/insights/<user_id>')
    async def user_insights(user_id: int):
        """Get learning insights for specific user"""
        try:
            insights = await LearningInsightsManager.get_user_insights(int(user_id))
            if insights:
                return jsonify(insights)
            return jsonify({"error": "No insights found"}), 404
        except Exception as e:
            logger.error(f"Error getting user insights: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/admin/insights/dashboard')
    async def insights_dashboard():
        """Get aggregated learning insights dashboard"""
        try:
            dashboard_data = await LearningInsightsManager.get_admin_dashboard_data()
            return jsonify(dashboard_data)
        except Exception as e:
            logger.error(f"Error getting insights dashboard: {e}")
            return jsonify({"error": str(e)}), 500
        
    @app.route('/feedback/personalization/<user_id>')
    @async_jwt_required()
    async def get_personalization_data(user_id):
        try:
            data = await FeedbackAnalyticsManager.get_personalization_data(user_id)
            return jsonify({"status": "success", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/feedback/templates/<template_key>')
    @async_jwt_required()
    async def get_template(template_key):
        try:
            template = FEEDBACK_TEMPLATES.get(template_key)
            return jsonify({"status": "success", "template": template})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
        
    @app.route('/link-telegram', methods=['POST'])
    @async_jwt_required()
    async def link_telegram():
        """Link Telegram account to existing web user"""
        try:
            data = await request.get_json()
            telegram_id = data.get('telegram_id')
            user_email = request.user_email
            
            if not telegram_id:
                return jsonify({
                    "status": "error",
                    "message": "Telegram ID is required"
                }), 400

            # Update user record with Telegram ID
            result = await db.users.update_one(
                {"email": user_email},
                {
                    "$set": {
                        "telegram_id": telegram_id,
                        "platforms": ["web", "telegram"]
                    }
                }
            )

            if result.modified_count > 0:
                return jsonify({
                    "status": "success",
                    "message": "Telegram account linked successfully"
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": "Failed to link account"
                }), 500

        except Exception as e:
            logger.error(f"Error linking Telegram account: {e}")
            return jsonify({
                "status": "error",
                "message": "Server error"
            }), 500