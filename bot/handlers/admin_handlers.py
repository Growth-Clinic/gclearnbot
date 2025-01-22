from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from services.database import TaskManager, FeedbackManager, UserManager, init_mongodb
from services.lesson_loader import load_lessons
from config.settings import Config
import logging

# Initialize database connection and load lessons
db = init_mongodb()
lessons = load_lessons()
ADMIN_IDS = Config.ADMIN_IDS

logger = logging.getLogger(__name__)


# Admin Commands
async def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS


async def adminhelp_command(update: Update, context: CallbackContext):
    """Send a list of admin commands with descriptions."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    help_text = """
    🤖 Admin Commands:

    /users - View a list of all users
    /viewfeedback - View all feedback submitted by users
    /processfeedback <feedback_id> - Mark feedback as processed
    /addtask <lesson_key> - Add a task to a lesson
    /listtasks - List all tasks
    /deactivatetask <task_id> - Deactivate a task
    /adminhelp - Show this help message
    """
    await update.message.reply_text(help_text)



async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all users"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    users_list = list(db.users.find())
    
    report = "📊 Users Report:\n\n"
    for user in users_list:
        # Only count main lessons (not steps)
        completed_main_lessons = len([lesson for lesson in user.get('completed_lessons', []) 
                                      if lesson.count('_') == 1])  # Only counts lesson_X format
        report += f"👤 User: {user.get('username') or user.get('first_name')}\n"
        report += f"📝 Current Lesson: {user.get('current_lesson')}\n"
        report += f"✅ Completed: {len(user.get('completed_lessons', []))} lessons\n\n"
    
    await update.message.reply_text(report)



async def view_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view all feedback"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        feedback_list = FeedbackManager.get_all_feedback()
        if not feedback_list:
            await update.message.reply_text("No feedback found.")
            return
            
        report = "📬 Feedback Report:\n\n"
        for feedback in feedback_list:
            feedback_id = feedback.get('id', 'Unknown')  # Fetch feedback ID
            user_id = feedback.get('user_id', 'Unknown')
            
            # Add more detailed error handling for user info retrieval
            try:
                user = await UserManager.get_user_info(user_id)
                username = user.get('username', 'Unknown') if user else f"User {user_id}"
            except Exception as e:
                logger.error(f"Error fetching user info for {user_id}: {e}")
                username = f"User {user_id}"
            
            # Add feedback details with ID, status, and category
            report += f"🆔 Feedback ID: {feedback_id}\n"
            report += f"👤 From: {username} (ID: {user_id})\n"
            report += f"📅 Time: {feedback.get('timestamp', 'Unknown time')}\n"
            report += f"💭 Message: {feedback.get('feedback', 'No message content')}\n"
            report += f"📌 Status: {'✅ Processed' if feedback.get('processed') else '⏳ Pending'}"
            if feedback.get('category'):
                report += f" (Category: {feedback['category']})"
            report += "\n------------------------\n\n"
        
        # Split long reports into multiple messages if needed
        if len(report) > 4096:
            for i in range(0, len(report), 4096):
                await update.message.reply_text(report[i:i+4096])
        else:
            await update.message.reply_text(report)
            
    except Exception as e:
        logger.error(f"Error viewing feedback: {e}", exc_info=True)
        await update.message.reply_text("Error retrieving feedback. Please try again later.")




async def process_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to mark feedback as processed."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Extract feedback_id and category from the command arguments
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Usage: /processfeedback <feedback_id> [category]")
            return
        
        feedback_id = args[0]
        category = args[1] if len(args) > 1 else None

        # Mark feedback as processed
        success = await FeedbackManager.mark_as_processed(feedback_id, category)
        if success:
            await update.message.reply_text(f"✅ Feedback {feedback_id} has been marked as processed.")
        else:
            await update.message.reply_text(f"⚠️ Could not process feedback {feedback_id}. Please check the ID.")

    except Exception as e:
        logger.error(f"Error processing feedback: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while processing the feedback. Please try again.")



async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to add a new task"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    usage = (
        "To add a task, use the following format:\n"
        "/addtask lesson_key\n"
        "Company Name\n"
        "Task Description\n"
        "Requirement 1\n"
        "Requirement 2\n"
        "...\n\n"
        "Example:\n"
        "/addtask lesson_2\n"
        "TechStartup Inc\n"
        "Design an onboarding flow for our mobile app\n"
        "- Experience with UX design\n"
        "- Knowledge of mobile design patterns"
    )

    try:
        if not update.message or not update.message.text:
            await update.message.reply_text(usage)
            return
            
        lines = update.message.text.split('\n')
        if len(lines) < 3:
            await update.message.reply_text(usage)
            return

        # Parse command and lesson key
        cmd_parts = lines[0].split()
        if len(cmd_parts) != 2:
            await update.message.reply_text(usage)
            return
            
        lesson_key = cmd_parts[1]
        
        # Validate lesson key
        if lesson_key not in lessons:
            await update.message.reply_text(f"Invalid lesson key. Available lessons: {', '.join(lessons.keys())}")
            return

        company = lines[1]
        description = lines[2]
        requirements = lines[3:] if len(lines) > 3 else []

        # Add the task
        task = TaskManager.add_task(company, lesson_key, description, requirements)
        
        if task:
            confirmation = f"""
✅ Task #{task['task_id']} added successfully!

📝 Task Details:
Lesson: {task['lesson']}
Company: {task['company']}
Description: {task['description']}
"""
            if task['requirements']:
                confirmation += "\nRequirements:\n" + "\n".join(f"- {req}" for req in task['requirements'])
            
            await update.message.reply_text(confirmation)
        else:
            await update.message.reply_text("Failed to create task. Please try again.")

    except Exception as e:
        logger.error(f"Error adding task: {e}")
        await update.message.reply_text("Error creating task. Please check the format and try again.")



async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to list all tasks with IDs"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        tasks = list(db.tasks.find())
        if not tasks:
            await update.message.reply_text("No tasks found.")
            return

        report = "📋 All Tasks:\n\n"
        for task in tasks:
            status = "🟢 Active" if task["is_active"] else "🔴 Inactive"
            report += f"Task #{task['task_id']} ({status})\n"
            report += f"Lesson: {task['lesson']}\n"
            report += f"Company: {task['company']}\n"
            report += f"Description: {task['description']}\n"
            if task["requirements"]:
                report += "Requirements:\n" + "\n".join(f"- {req}" for req in task["requirements"])
            report += "\n\n"

        await update.message.reply_text(report)

    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        await update.message.reply_text("Error retrieving tasks. Please try again.")



async def deactivate_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to deactivate a task"""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Command format: /deactivatetask task_id
        task_id = int(context.args[0])
        TaskManager.deactivate_task(task_id)
        await update.message.reply_text(f"Task #{task_id} has been deactivated.")
    except (IndexError, ValueError):
        await update.message.reply_text("Please provide a valid task ID: /deactivatetask <task_id>")



def format_task_report(task):
    """Helper function to format task details without f-strings"""
    status = "🟢 Active" if task["is_active"] else "🔴 Inactive"
    lines = [
        f"Task #{task['id']} ({status})",
        f"Company: {task['company']}",
        f"Lesson: {task['lesson']}",
        f"Description: {task['description']}"
    ]
    
    if task["requirements"]:
        lines.append("Requirements:")
        for req in task["requirements"]:
            lines.append(f"- {req}")
    
    return "\n".join(lines)