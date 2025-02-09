from quart import Quart, request, jsonify, ResponseReturnValue, send_from_directory
from services.database import db, AnalyticsManager, UserManager, JournalManager
from services.lesson_manager import LessonService
from services.progress_tracker import ProgressTracker
from services.learning_insights import LearningInsightsManager
from services.content_loader import content_loader
from datetime import datetime, timezone
import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application
import json
import bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import jwt

logger = logging.getLogger(__name__)

app = Quart(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")  # Use Render environment variable
jwt = JWTManager(app)  # Initialize JWT authentication

def setup_routes(app: Quart, application: Application) -> None:

    """Set up API routes for web access"""

    lesson_service = LessonService(task_manager=None, user_manager=UserManager())  # Adjust as needed
    progress_tracker = ProgressTracker()

    @app.route('/register', methods=['POST'])
    async def register():
        """User registration"""
        try:
            data = await request.json
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return jsonify({"status": "error", "message": "Email and password required"}), 400

            # Check if user exists
            existing_user = await db.users.find_one({"email": email})
            if existing_user:
                return jsonify({"status": "error", "message": "User already exists"}), 400

            # Hash password before storing
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

            # Save user in MongoDB
            await db.users.insert_one({"email": email, "password": hashed_pw})

            return jsonify({"status": "success", "message": "User registered successfully"}), 201

        except Exception as e:
            logger.error(f"Registration error: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    
    @app.route('/login', methods=['POST'])
    async def login():
        """User login & sync progress from Telegram"""
        try:
            data = await request.json
            email = data.get("email")
            password = data.get("password")

            user = await db.users.find_one({"email": email})
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 401

            if "password" in user:
                # Web user: Check password
                if not bcrypt.checkpw(password.encode(), user["password"].encode()):
                    return jsonify({"status": "error", "message": "Invalid password"}), 401
            else:
                # Telegram-only user: Allow login without password
                await db.users.update_one({"email": email}, {"$set": {"password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()}})
            
            # Generate JWT token
            access_token = create_access_token(identity=email, expires_delta=datetime.timedelta(days=1))

            return jsonify({"status": "success", "token": access_token}), 200

        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500
        

    @app.route('/protected', methods=['GET'])
    @jwt_required()
    async def protected():
        """Example protected route"""
        current_user = get_jwt_identity()
        return jsonify(logged_in_as=current_user), 200
    
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
    async def submit_lesson_response(lesson_id):
        """Submit a user response for a lesson"""
        try:
            data = await request.json
            user_id = str(data.get("user_id"))
            response_text = data.get("response")

            if not user_id or not response_text:
                return jsonify({"status": "error", "message": "Missing user_id or response"}), 400

            # Save journal entry
            await JournalManager.save_journal_entry(user_id, lesson_id, response_text)

            # Update progress
            await UserManager.update_user_progress(user_id, lesson_id)

            return jsonify({"status": "success", "message": "Response saved"}), 200

        except Exception as e:
            logger.error(f"Error submitting response for lesson {lesson_id}: {e}")
            return jsonify({"status": "error", "message": "Server error"}), 500

    @app.route('/progress', methods=['GET'])
    @jwt_required()
    async def get_progress():
        """Fetch user progress based on email"""
        try:
            email = get_jwt_identity()  # Get email from JWT token
            user_data = await db.users.find_one({"email": email})

            if not user_data:
                return jsonify({"status": "error", "message": "User not found"}), 404

            return jsonify({"status": "success", "progress": user_data.get("progress", {})}), 200

        except Exception as e:
            logger.error(f"Error fetching progress for user {email}: {e}")
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

    @app.route('/journal/<user_id>', methods=['GET'])
    async def get_journal(user_id):
        """Fetch user's journal entries"""
        try:
            journal = await JournalManager.get_user_journal(user_id)
            if journal:
                return jsonify({"status": "success", "journal": journal["entries"]}), 200
            return jsonify({"status": "error", "message": "No journal entries found"}), 404
        except Exception as e:
            logger.error(f"Error fetching journal for user {user_id}: {e}")
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