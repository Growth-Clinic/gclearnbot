from slack_bolt import App
from services.database import UserManager, JournalManager
from services.progress_tracker import ProgressTracker
import logging

logger = logging.getLogger(__name__)

def init_slack_commands(app: App) -> None:
    """Initialize Slack command handlers"""
    
    @app.command("/resume")
    async def handle_resume(ack, say, command):
        """Handle the /resume command"""
        await ack()
        try:
            user_id = command["user_id"]
            user_data = await UserManager.get_user_info(user_id)
            
            if user_data and user_data.get("current_lesson"):
                blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📚 Resuming your last lesson..."
                    }
                }]
                await say(blocks=blocks)
                # Main resume logic handled in handlers.py
            else:
                await say("No previous progress found. Use `/start` to begin!")
                
        except Exception as e:
            logger.error(f"Error handling resume command: {e}")
            await say("Error resuming progress. Please try again.")

    @app.command("/journal")
    async def handle_journal(ack, say, command):
        """Handle the /journal command"""
        await ack()
        try:
            user_id = command["user_id"]
            journal = await JournalManager.get_user_journal(user_id)
            
            if journal and journal.get("entries"):
                blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📖 *Your Learning Journal*"
                    }
                }]
                
                for entry in journal["entries"][-5:]:  # Show last 5 entries
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Lesson:* {entry['lesson']}\n*Response:* {entry['response']}\n*Date:* {entry['timestamp']}\n"
                        }
                    })
                
                await say(blocks=blocks)
            else:
                await say("No journal entries found yet. Complete some lessons first!")
                
        except Exception as e:
            logger.error(f"Error handling journal command: {e}")
            await say("Error retrieving journal. Please try again.")

    @app.command("/progress")
    async def handle_progress(ack, say, command):
        """Handle the /progress command"""
        await ack()
        try:
            user_id = command["user_id"]
            progress_data = await ProgressTracker.get_complete_progress(user_id)
            
            if progress_data:
                blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📊 *Learning Progress Report*"
                    }
                }]

                # Overall Progress
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"""
*Overall Progress*
• Completion: {progress_data.get('completion_rate', 0)}%
• Total Responses: {progress_data.get('total_responses', 0)}
• Learning Duration: {progress_data.get('learning_duration_days', 0)} days
"""
                    }
                })

                # Engagement Stats
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"""
*Engagement*
• Engagement Score: {progress_data.get('engagement_score', 0)}/100
• Avg Response Length: {progress_data.get('average_response_length', 0)} words
"""
                    }
                })

                # Add streak info if available
                if progress_data.get('current_streak'):
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🔥 Current Streak: {progress_data.get('current_streak')} days"
                        }
                    })

                await say(blocks=blocks)
            else:
                await say("No progress data available yet. Start your learning journey! 🌱")
                
        except Exception as e:
            logger.error(f"Error handling progress command: {e}")
            await say("Error retrieving progress. Please try again.")

    @app.command("/help")
    async def handle_help(ack, say):
        """Handle the /help command"""
        await ack()
        try:
            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": """
🤖 *Available Commands*

• `/start` - Start or restart the learning journey
• `/resume` - Continue from your last lesson
• `/journal` - View your learning journal entries
• `/help` - Show this help message

To progress through lessons:
1. Read the lesson content
2. Complete the given task
3. Send your response
4. Click Continue when prompted

Your responses are automatically saved to your learning journal.
"""
                }
            }]
            await say(blocks=blocks)
            
        except Exception as e:
            logger.error(f"Error handling help command: {e}")
            await say("Error displaying help. Please try again.")