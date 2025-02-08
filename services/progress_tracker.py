from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional
from services.database import JournalManager, UserManager, AnalyticsManager

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Handles user progress tracking and streak management"""
    
    @staticmethod
    def calculate_streak(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive streak information."""
        if not entries:
            return {"current_streak": 0, "longest_streak": 0, "total_days": 0}
            
        try:
            # Sort entries by timestamp
            sorted_entries = sorted(entries, key=lambda x: x['timestamp'], reverse=True)
            
            # Calculate current streak
            current_streak = 1
            longest_streak = 1
            current_streak_start = datetime.fromisoformat(sorted_entries[0]['timestamp'].replace('Z', '+00:00')).date()
            
            # Track streaks
            temp_streak = 1
            last_date = current_streak_start
            
            for entry in sorted_entries[1:]:
                entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).date()
                days_diff = (last_date - entry_date).days
                
                if days_diff == 1:
                    temp_streak += 1
                    longest_streak = max(longest_streak, temp_streak)
                    current_streak = temp_streak
                elif days_diff > 1:
                    temp_streak = 1
                    if entry_date != current_streak_start:
                        break
                        
                last_date = entry_date
            
            # Calculate total active days
            unique_days = len(set(datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).date() 
                               for entry in entries))
            
            return {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "total_days": unique_days
            }
            
        except Exception as e:
            logger.error(f"Error calculating streak details: {e}")
            return {"current_streak": 0, "longest_streak": 0, "total_days": 0}

    @staticmethod
    def get_streak_milestone_message(streak_info: Dict[str, Any]) -> Optional[str]:
        """Generate milestone messages for significant streak achievements."""
        current_streak = streak_info["current_streak"]
        longest_streak = streak_info["longest_streak"]
        
        # Check for new milestones
        if isinstance(current_streak, (int, float)):  # Add type checking
            if current_streak >= 30:
                return "🏆 *Incredible Achievement!* You've maintained your reflection practice for 30 days!"
            elif current_streak >= 21:
                return "⭐ *Major Milestone!* Three weeks of consistent reflection!"
            elif current_streak >= 14:
                return "💫 *Fantastic Progress!* You've completed two weeks of regular practice!"
            elif current_streak >= 7:
                return "🔥 *Wonderful Work!* A full week of daily reflections!"
            elif current_streak >= 3:
                return "✨ *Great Start!* Three days of consistent practice!"
            elif isinstance(longest_streak, (int, float)) and current_streak > longest_streak:  # Add type checking
                return "🌟 *New Record!* This is your longest streak yet!"
        
        return None

    @staticmethod
    def format_progress_message(journal_entries: List[Dict[str, Any]], 
                              quality_metrics: Dict[str, Any],
                              total_lessons: int = 24) -> str:
        """Format progress information with enhanced streak details."""
        try:
            if not journal_entries:
                return "📊 *No entries yet!*\nStart your learning journey with your first entry! 🌱"

            # Get comprehensive streak information
            streak_info = ProgressTracker.calculate_streak(journal_entries)
            
            # Calculate completion metrics
            completed_lessons = len(set(entry['lesson'] for entry in journal_entries))
            completion_rate = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
            
            # Create progress bar
            filled = int(completion_rate / 10)
            progress_bar = "▰" * filled + "▱" * (10 - filled)
            
            # Format message
            message = "*📊 Progress Dashboard*\n\n"
            
            # Progress section
            message += f"*Progress:* {completion_rate:.1f}%\n"
            message += f"{progress_bar}\n"
            message += f"• Completed: {completed_lessons}/{total_lessons} lessons\n"
            
            # Enhanced streak section
            message += "\n*🔥 Streak Stats:*\n"
            message += f"• Current Streak: {streak_info['current_streak']} days\n"
            message += f"• Longest Streak: {streak_info['longest_streak']} days\n"
            message += f"• Total Active Days: {streak_info['total_days']}\n"
            
            # Add milestone message if applicable
            milestone_msg = ProgressTracker.get_streak_milestone_message(streak_info)
            if milestone_msg:
                message += f"\n{milestone_msg}\n"
            
            # Response quality section
            if quality_metrics and quality_metrics.get('word_count', 0) > 0:
                message += f"\n*📝 Latest Response:*\n"
                message += f"• Length: {quality_metrics['word_count']} words\n"
                if quality_metrics.get('word_count', 0) >= 50:
                    message += "• Excellent detail! ⭐\n"
                elif quality_metrics.get('word_count', 0) >= 30:
                    message += "• Good length! ✨\n"
                    
            return message
            
        except Exception as e:
            logger.error(f"Error formatting progress message: {e}")
            return "Error generating progress update. Please try again."

    @staticmethod
    async def get_complete_progress(user_id: int) -> str:
        """Generate a complete progress summary."""
        try:
            # Get user metrics
            metrics = await AnalyticsManager.calculate_user_metrics(user_id)
            if not metrics:
                return "No progress data available yet. Start your learning journey! 🌱"

            # Format message with Telegram markdown
            message = "*📊 Complete Progress Report*\n\n"

            # Overall Progress
            message += "*Overall Progress*\n"
            message += f"• Completion: {metrics.get('completion_rate', 0):.1f}%\n"
            message += f"• Total Responses: {metrics.get('total_responses', 0)}\n"
            message += f"• Learning Duration: {metrics.get('learning_duration_days', 0)} days\n"

            # Engagement Stats
            message += "\n*Engagement*\n"
            message += f"• Engagement Score: {metrics.get('engagement_score', 0):.1f}/100\n"
            message += f"• Avg Response Length: {metrics.get('average_response_length', 0)} words\n"
            
            # Get journal entries for streak
            journal = await JournalManager.get_user_journal(user_id)
            if journal and journal.get('entries'):
                streak_info = ProgressTracker.calculate_streak(journal['entries'])
                if streak_info.get('current_streak', 0) > 0:
                    message += f"• Current Streak: {streak_info['current_streak']} days 🔥\n"

            # Learning Pattern Analysis
            message += "\n*Learning Pattern*\n"
            if avg_days := metrics.get('avg_days_between_lessons'):
                message += f"• Learning Pace: {avg_days:.1f} days between lessons\n"
            
            # Add encouragement based on metrics
            message += "\n" + ProgressTracker.get_encouragement_message(
                metrics.get('completion_rate', 0),
                metrics.get('engagement_score', 0)
            )

            return message

        except Exception as e:
            logger.error(f"Error generating complete progress: {e}")
            return "Error generating progress report. Please try again later."

    @staticmethod
    def get_encouragement_message(completion_rate: float, engagement_score: float) -> str:
        """Generate contextual encouragement message."""
        if completion_rate >= 80 and engagement_score >= 80:
            return "🌟 Outstanding progress! You're mastering the content!"
        elif completion_rate >= 50 or engagement_score >= 50:
            return "💪 Great work! Keep up the momentum!"
        else:
            return "🌱 You're on your way! Every step counts!"