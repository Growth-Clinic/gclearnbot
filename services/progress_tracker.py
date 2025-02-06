from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Handles user progress tracking and formatting"""
    
    @staticmethod
    def calculate_streak(entries: List[Dict[str, Any]]) -> int:
        """Calculate user's current streak of consecutive days with entries."""
        if not entries:
            return 0
            
        try:
            # Sort entries by timestamp
            sorted_entries = sorted(entries, key=lambda x: x['timestamp'], reverse=True)
            
            streak = 1
            last_date = datetime.fromisoformat(sorted_entries[0]['timestamp'].replace('Z', '+00:00')).date()
            
            for entry in sorted_entries[1:]:
                entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).date()
                if (last_date - entry_date).days == 1:
                    streak += 1
                    last_date = entry_date
                elif (last_date - entry_date).days > 1:
                    break
                    
            return streak
            
        except Exception as e:
            logger.error(f"Error calculating streak: {e}")
            return 0

    @staticmethod
    def format_progress_message(journal_entries: List[Dict[str, Any]], 
                              quality_metrics: Dict[str, Any],
                              total_lessons: int = 24) -> str:
        """Format progress information into a Telegram message."""
        try:
            if not journal_entries:
                return "📊 No entries yet. Keep going!"

            # Calculate basic metrics
            total_entries = len(journal_entries)
            current_streak = ProgressTracker.calculate_streak(journal_entries)
            
            # Calculate completion metrics
            completed_lessons = len(set(entry['lesson'] for entry in journal_entries))
            completion_rate = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
            
            # Create progress bar (10 segments)
            filled_blocks = int(completion_rate / 10)
            progress_bar = "▓" * filled_blocks + "░" * (10 - filled_blocks)
            
            # Format the message
            message = "📊 *Progress Update*\n\n"
            
            # Overall progress
            message += f"*Overall Progress*\n"
            message += f"|{progress_bar}| {completion_rate:.1f}%\n"
            message += f"• Completed {completed_lessons}/{total_lessons} lessons\n"
            message += f"• Total entries: {total_entries}\n"
            
            # Streak information
            if current_streak > 1:
                message += f"\n🔥 *Current Streak*: {current_streak} days\n"
                if current_streak >= 7:
                    message += "Amazing dedication! Keep it up! 🌟\n"
                else:
                    message += "You're building momentum! 💪\n"
            
            # Response quality (if metrics provided)
            if quality_metrics:
                message += f"\n📝 *Latest Response*\n"
                message += f"• Length: {quality_metrics.get('word_count', 0)} words\n"
                if quality_metrics.get('word_count', 0) > 50:
                    message += "Excellent detailed response! ✨\n"
                elif quality_metrics.get('word_count', 0) > 30:
                    message += "Good level of detail! 👍\n"
                
                if quality_metrics.get('has_punctuation'):
                    message += "Well structured with good punctuation! 📖\n"
            
            # Add encouragement
            message += f"\n{ProgressTracker.get_encouragement_message(current_streak, total_entries)}"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting progress message: {e}")
            return "Error generating progress update. Please try again."

    @staticmethod
    def get_encouragement_message(streak: int, entries_count: int) -> str:
        """Get contextual encouragement message based on user's progress."""
        if streak >= 7:
            return "🌟 Incredible streak! You're making outstanding progress!"
        elif streak >= 3:
            return "🔥 Great consistency! Keep the momentum going!"
        elif entries_count > 10:
            return "💪 You're building a strong learning habit!"
        elif entries_count > 0:
            return "👍 Every entry helps you grow. Keep going!"
        return "🌱 Start your learning journey with your first entry!"