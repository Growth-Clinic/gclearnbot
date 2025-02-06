from telegram import Update
from telegram.ext import ContextTypes
from services.database import TaskManager, FeedbackManager, UserManager, init_mongodb, AnalyticsManager
from services.content_loader import content_loader
from services.learning_insights import LearningInsightsManager
from config.settings import Config
import logging

# Initialize database connection and load lessons
db = init_mongodb()
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
    /learninginsights - View learning insights dashboard
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


async def learning_insights_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view learning insights dashboard."""
    if not await is_admin(update.message.from_user.id):
        await update.message.reply_text("This command is only available to admins.")
        return

    try:
        dashboard_data = await LearningInsightsManager.get_admin_dashboard_data()
        
        report = "📊 Learning Insights Dashboard\n\n"
        
        # Overall Statistics
        report += f"👥 Total Users Analyzed: {dashboard_data['total_users_analyzed']}\n\n"
        
        # Common Support Areas
        report += "🎯 Common Support Areas:\n"
        for area in dashboard_data['common_support_areas']:
            report += f"- {area['area']}: {area['count']} users\n"
            
        # Emerging Trends
        report += "\n📈 Emerging Trends:\n"
        for trend in dashboard_data['emerging_trends']:
            report += f"- {trend['trend']}: {trend['count']} occurrences\n"
        
        await update.message.reply_text(report)
        
    except Exception as e:
        logger.error(f"Error generating learning insights: {e}")
        await update.message.reply_text("Error generating insights. Please try again later.")


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