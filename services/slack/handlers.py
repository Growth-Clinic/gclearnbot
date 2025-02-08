from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import logging
from datetime import datetime, timezone
from services.progress_tracker import ProgressTracker
from services.database import UserManager, JournalManager, TaskManager
from services.lesson_manager import LessonService
from services.content_loader import content_loader
from services.feedback_enhanced import evaluate_response_enhanced, analyze_response_quality, format_feedback_message
from config.settings import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Slack app
app = App(token=Config.SLACK_BOT_TOKEN)
logger.info("Initializing Slack bot...")

# Initialize services
lesson_service = LessonService(
    task_manager=TaskManager(),
    user_manager=UserManager()
)

async def handle_start_command(body, say, client):
    """Handle the /start command"""
    try:
        user_id = body['user_id']
        
        # Save user info
        user_info = await client.users_info(user=user_id)
        user = user_info['user']
        await UserManager.save_user_info({
            'user_id': user_id,
            'username': user.get('name'),
            'first_name': user.get('real_name'),
            'language_code': 'en',  # Slack doesn't provide language, default to English
            'joined_date': user.get('updated')
        })

        # Get main lessons
        lessons = content_loader.get_full_lessons()
        
        # Create lesson buttons
        blocks = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Welcome to Growth Clinic! 🌱\n\nReady to future-proof your career? Choose your learning path:"
            }
        }]
        
        # Add lesson choices as buttons
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

async def handle_lesson_choice(body, say, ack):
    """Handle lesson choice button clicks"""
    try:
        await ack()
        user_id = body['user']['id']
        lesson_id = body['actions'][0]['value']
        
        # Update user progress
        success = await UserManager.update_user_progress(user_id, lesson_id)
        
        if success:
            # Get lesson content
            lessons = content_loader.load_content('lessons')
            lesson = lessons.get(lesson_id)
            
            if lesson:
                # Format message with lesson content
                blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": lesson['text']
                    }
                }]
                
                # Add next button if available
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
                await say("Sorry, I couldn't find that lesson. Please try /start again.")
        else:
            await say("Error updating progress. Please try again.")
            
    except Exception as e:
        logger.error(f"Error handling lesson choice: {e}")
        await say("Sorry, something went wrong. Please try again.")

async def handle_message(message, say):
    """Enhanced message handling with better error handling and feedback"""
    try:
        user_id = message['user']
        text = message['text']
        
        # Get user's current lesson with explicit error handling
        user_data = await UserManager.get_user_info(user_id)
        if not user_data:
            logger.warning(f"No user data found for user {user_id}")
            await say("Please use /start to begin your learning journey.")
            return
            
        current_lesson = user_data.get("current_lesson")
        if not current_lesson:
            logger.warning(f"No current lesson found for user {user_id}")
            await say("Please use /start to begin your learning journey.")
            return
            
        # Add request logging
        logger.info(f"Processing message from user {user_id} for lesson {current_lesson}")
        
        # Save journal entry with timestamp
        entry_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lesson": current_lesson,
            "response": text,
            "response_length": len(text)
        }
        
        save_success = await JournalManager.save_journal_entry(user_id, current_lesson, text)
        if not save_success:
            logger.error(f"Failed to save journal entry for user {user_id}")
            await say("There was an error saving your response. Please try again.")
            return
            
        # Enhanced response evaluation
        feedback = evaluate_response_enhanced(current_lesson, text, user_id)
        quality_metrics = analyze_response_quality(text)
        
        # Format feedback with progress information
        feedback_message = await format_feedback_message(feedback, quality_metrics, user_id)
        
        # Get user progress for additional context
        progress_tracker = ProgressTracker()
        journal = await JournalManager.get_user_journal(user_id)
        if journal and journal.get('entries'):
            progress_message = progress_tracker.format_progress_message(
                journal['entries'],
                quality_metrics
            )
            feedback_message += f"\n\n{progress_message}"
        
        # Send enhanced feedback
        await say(feedback_message)
        
        # Progress to next lesson if available
        lessons = content_loader.load_content('lessons')
        lesson_data = lessons.get(current_lesson, {})
        next_step = lesson_data.get("next")
        
        if next_step:
            success = await UserManager.update_user_progress(user_id, next_step)
            if success:
                lesson = lessons.get(next_step)
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
                    logger.error(f"Next lesson {next_step} not found")
                    await say("Error loading next lesson. Please use /resume to continue.")
            else:
                logger.error(f"Failed to update progress for user {user_id}")
                await say("Error updating progress. Please use /resume to continue.")
        else:
            await say("✅ Response saved! You've completed all lessons.")
            
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await say("I encountered an error processing your response. Please try again.")

# Register command handlers
app.command("/start")(handle_start_command)

# Register action handlers
app.action("lesson_choice_.*")(handle_lesson_choice)
app.action("lesson_next_.*")(handle_lesson_choice)

# Register message handler
app.message("")(handle_message)

def start_slack_bot():
    """Start the Slack bot"""
    handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)
    handler.start()