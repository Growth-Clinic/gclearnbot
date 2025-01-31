from telegram import Update
from telegram.ext import ContextTypes
from services.database import TaskManager, FeedbackManager, UserManager, init_mongodb, AnalyticsManager
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


async def adminhelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of admin commands with descriptions."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    help_text = """
    🤖 Admin Commands:

    /analytics - View overall analytics dashboard
    /useranalytics <user_id> - View analytics for a specific user
    /lessonanalytics <lesson_key> - View analytics for a specific lesson
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
        report += f"👤 User: {user.get('username') or user.get('first_name')}\n"
        report += f"🆔 User ID: {user['user_id']}\n"
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



async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view analytics dashboard."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Get cohort metrics
        cohort_metrics = AnalyticsManager.calculate_cohort_metrics()
        
        # Format the analytics report
        report = "📊 Learning Analytics Dashboard\n\n"
        
        # Overall Statistics
        report += "👥 User Statistics:\n"
        report += f"- Total Users: {cohort_metrics.get('total_users', 0)}\n"
        report += f"- Average Completion Rate: {cohort_metrics.get('average_completion_rate', 0)}%\n"
        
        # Active Users
        active_users = cohort_metrics.get('active_users', {})
        report += "\n📱 Active Users:\n"
        report += f"- Last 24 hours: {active_users.get('last_24h', 0)}\n"
        report += f"- Last 7 days: {active_users.get('last_7d', 0)}\n"
        
        # Retention Rates
        retention = cohort_metrics.get('retention_rates', {})
        report += "\n📈 Retention Rates:\n"
        report += f"- Daily: {retention.get('daily', 0)}%\n"
        report += f"- Weekly: {retention.get('weekly', 0)}%\n"
        
        # Lesson Distribution
        lesson_dist = cohort_metrics.get('lesson_distribution', {})
        report += "\n📚 Current Lesson Distribution:\n"
        for lesson, count in lesson_dist.items():
            report += f"- {lesson}: {count} users\n"
        
        await update.message.reply_text(report)
        
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        await update.message.reply_text("Error generating analytics. Please try again later.")

async def user_analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view analytics for a specific user."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Check if user ID was provided
        if not context.args:
            await update.message.reply_text("Please provide a user ID: /useranalytics <user_id>")
            return
            
        user_id = int(context.args[0])
        metrics = AnalyticsManager.calculate_user_metrics(user_id)
        
        if not metrics:
            await update.message.reply_text("No data found for this user.")
            return
        
        # Format the user analytics report
        report = f"📊 User Analytics for ID: {user_id}\n\n"
        
        # Progress Metrics
        report += "📚 Learning Progress:\n"
        report += f"- Completed Lessons: {metrics.get('completed_lessons', 0)}\n"
        report += f"- Completion Rate: {metrics.get('completion_rate', 0)}%\n"
        report += f"- Current Lesson: {metrics.get('current_lesson', 'None')}\n"
        
        # Engagement Metrics
        report += "\n💡 Engagement Metrics:\n"
        report += f"- Total Responses: {metrics.get('total_responses', 0)}\n"
        report += f"- Average Response Length: {metrics.get('average_response_length', 0)} characters\n"
        report += f"- Engagement Score: {metrics.get('engagement_score', 0)}/100\n"
        
        # Time Metrics
        report += "\n⏱️ Time Metrics:\n"
        report += f"- Learning Duration: {metrics.get('learning_duration_days', 0)} days\n"
        report += f"- Avg Days Between Lessons: {metrics.get('avg_days_between_lessons', 0)}\n"
        report += f"- Last Active: {metrics.get('last_active', 'Never')}\n"
        
        await update.message.reply_text(report)
        
    except ValueError:
        await update.message.reply_text("Please provide a valid user ID number.")
    except Exception as e:
        logger.error(f"Error generating user analytics: {e}")
        await update.message.reply_text("Error generating analytics. Please try again later.")

async def lesson_analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view analytics for a specific lesson."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        # Check if lesson key was provided
        if not context.args:
            await update.message.reply_text("Please provide a lesson key: /lessonanalytics <lesson_key>")
            return
            
        lesson_key = context.args[0]
        analytics = AnalyticsManager.get_lesson_analytics(lesson_key)
        
        if not analytics:
            await update.message.reply_text("No data found for this lesson.")
            return
        
        # Format the lesson analytics report
        report = f"📊 Lesson Analytics for: {lesson_key}\n\n"
        
        # Response Metrics
        report += "📝 Response Metrics:\n"
        report += f"- Total Responses: {analytics.get('total_responses', 0)}\n"
        report += f"- Unique Completions: {analytics.get('unique_completions', 0)}\n"
        report += f"- Average Response Length: {analytics.get('average_response_length', 0)} characters\n"
        report += f"- Responses Per Day: {analytics.get('responses_per_day', 0)}\n"
        
        # Keyword Analysis
        keyword_freq = analytics.get('keyword_frequency', {})
        if keyword_freq:
            report += "\n🔍 Top Keywords Used:\n"
            sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            for keyword, frequency in sorted_keywords:
                report += f"- {keyword}: {frequency} times\n"
        
        await update.message.reply_text(report)
        
    except Exception as e:
        logger.error(f"Error generating lesson analytics: {e}")
        await update.message.reply_text("Error generating analytics. Please try again later.")



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