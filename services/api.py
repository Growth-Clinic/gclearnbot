from quart import Quart, request, jsonify, ResponseReturnValue
from services.database import db, AnalyticsManager
from datetime import datetime, timezone
import asyncio
import logging
from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)


def setup_routes(app: Quart, application: Application) -> None:
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