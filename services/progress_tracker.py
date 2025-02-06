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
        """Format progress information into a visually appealing Telegram message."""
        try:
            if not journal_entries:
                return "📊 *No entries yet!*\nStart your learning journey with your first entry! 🌱"

            # Calculate basic metrics
            total_entries = len(journal_entries)
            current_streak = ProgressTracker.calculate_streak(journal_entries)
            
            # Calculate completion metrics
            completed_lessons = len(set(entry['lesson'] for entry in journal_entries))
            completion_rate = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
            
            # Create progress bar (10 segments)
            filled = int(completion_rate / 10)
            progress_bar = "▰" * filled + "▱" * (10 - filled)
            
            # Format the message with Telegram markdown
            message = "*📊 Progress Dashboard*\n\n"
            
            # Overall progress section
            message += f"*Progress:* {completion_rate:.1f}%\n"
            message += f"{progress_bar}\n"
            message += f"• Completed: {completed_lessons}/{total_lessons} lessons\n"
            
            # Streak section with dynamic emoji
            if current_streak > 0:
                streak_emoji = "🔥" if current_streak >= 3 else "✨"
                message += f"\n*{streak_emoji} Streak:* {current_streak} days\n"
            
            # Latest response quality (if metrics provided)
            if quality_metrics and quality_metrics.get('word_count', 0) > 0:
                message += f"\n*📝 Latest Response:*\n"
                message += f"• Length: {quality_metrics['word_count']} words\n"
                
                # Add quality indicators
                if quality_metrics.get('word_count', 0) >= 50:
                    message += "• Excellent detail! ⭐\n"
                elif quality_metrics.get('word_count', 0) >= 30:
                    message += "• Good length! ✨\n"
                    
            return message
            
        except Exception as e:
            logger.error(f"Error formatting progress message: {e}")
            return "Error generating progress update. Please try again."