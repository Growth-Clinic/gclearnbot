from slack_bolt import App
from services.database import UserManager, JournalManager, TaskManager
from services.progress_tracker import ProgressTracker
from services.content_loader import content_loader
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def init_slack_commands(app: App) -> None:
    """Initialize Slack command handlers"""
    
    @app.command("/start")
    async def handle_start(ack, say, command):
        """Handle the /start command"""
        await ack()
        try:
            user_id = command["user_id"]
            
            # Save user info
            await UserManager.save_user_info({
                'user_id': user_id,
                'platform': 'slack'
            })

            # Get main lessons
            lessons = content_loader.get_full_lessons(platform='slack')
            
            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Welcome to Growth Clinic! 🌱\n\nReady to future-proof your career? Choose your learning path:"
                }
            }]
            
            for lesson_id, lesson in lessons.items():
                if (lesson_id != "lesson_1" and 
                    not "congratulations" in lesson_id.lower() and 
                    lesson.get("type") == "full_lesson"):
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{lesson.get('description')}*"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Start"
                            },
                            "value": lesson_id,
                            "action_id": f"lesson_choice_{lesson_id}"
                        }
                    })

            await say(blocks=blocks)
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await say("Sorry, something went wrong. Please try again.")

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
                
                # Get lesson content
                lessons = content_loader.load_content('lessons')
                lesson = lessons.get(user_data["current_lesson"])
                if lesson:
                    blocks = [{
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": lesson['text']
                        }
                    }]
                    
                    if lesson.get('next'):
                        blocks.append({
                            "type": "actions",
                            "elements": [{
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Continue"
                                },
                                "value": lesson['next'],
                                "action_id": f"lesson_next_{lesson['next']}"
                            }]
                        })
                    
                    await say(blocks=blocks)
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
                
                # Show last 5 entries
                for entry in journal["entries"][-5:]:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Lesson:* {entry['lesson']}\n*Response:* {entry['response'][:200]}...\n*Date:* {entry['timestamp']}\n"
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
            progress_tracker = ProgressTracker()
            progress_data = await progress_tracker.get_complete_progress(user_id, platform='slack')
            
            if progress_data.get('blocks'):
                await say(blocks=progress_data['blocks'])
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
• `/progress` - Get a complete progress report
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

    # Add error handler for commands
    @app.error
    async def handle_errors(error, logger):
        """Global error handler for Slack commands"""
        logger.error(f"Error in Slack command: {error}")