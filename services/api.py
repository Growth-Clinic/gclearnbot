from quart import Quart, request, jsonify, ResponseReturnValue
from services.database import db, AnalyticsManager, UserManager, JournalManager
from services.lesson_manager import LessonService
from services.progress_tracker import ProgressTracker
from services.learning_insights import LearningInsightsManager
from datetime import datetime, timezone
import asyncio
import logging
from telegram import Update
from telegram.ext import Application
import json

logger = logging.getLogger(__name__)


def setup_routes(app: Quart, application: Application) -> None:

    """Set up API routes for web access"""

    lesson_service = LessonService(task_manager=None, user_manager=UserManager())  # Adjust as needed
    progress_tracker = ProgressTracker()

    @app.route('/lessons/<lesson_id>', methods=['GET'])
    async def get_lesson(lesson_id):
        """Fetch a specific lesson"""
        try:
            lesson = await db.lessons.find_one({"lesson_id": lesson_id}, {"_id": 0})
            if lesson:
                return jsonify({"status": "success", "lesson": lesson}), 200
            return jsonify({"status": "error", "message": "Lesson not found"}), 404
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

    @app.route('/progress/<user_id>', methods=['GET'])
    async def get_progress(user_id):
        """Fetch user progress"""
        try:
            user_data = await UserManager.get_user_info(user_id)
            if user_data:
                return jsonify({"status": "success", "progress": user_data.get("progress_metrics", {})}), 200
            return jsonify({"status": "error", "message": "User not found"}), 404
        except Exception as e:
            logger.error(f"Error fetching progress for user {user_id}: {e}")
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