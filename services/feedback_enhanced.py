from functools import lru_cache
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from services.feedback_config import LESSON_FEEDBACK_RULES

logger = logging.getLogger(__name__)

# Cache for feedback rules
@lru_cache(maxsize=32)
def get_feedback_rules(lesson_id: str) -> Dict[str, Any]:
    """
    Get cached feedback rules for a lesson.
    
    Args:
        lesson_id: The lesson identifier
        
    Returns:
        Dictionary containing feedback rules
    """
    return LESSON_FEEDBACK_RULES.get(lesson_id, {})

class FeedbackCache:
    """Manages caching of user responses and feedback"""
    _cache = {}
    _cache_timeout = timedelta(minutes=30)

    @classmethod
    def get_cached_feedback(cls, user_id: int, lesson_id: str) -> Optional[str]:
        """Get cached feedback if available and not expired"""
        cache_key = f"{user_id}_{lesson_id}"
        if cache_key in cls._cache:
            cached_data = cls._cache[cache_key]
            if datetime.now() - cached_data['timestamp'] < cls._cache_timeout:
                return cached_data['feedback']
            else:
                del cls._cache[cache_key]
        return None

    @classmethod
    def cache_feedback(cls, user_id: int, lesson_id: str, feedback: str) -> None:
        """Cache feedback for a user and lesson"""
        cache_key = f"{user_id}_{lesson_id}"
        cls._cache[cache_key] = {
            'feedback': feedback,
            'timestamp': datetime.now()
        }

def evaluate_response_enhanced(lesson_id: str, response_text: str, user_id: int) -> List[str]:
    """
    Enhanced response evaluation with caching and improved feedback.
    
    Args:
        lesson_id: Lesson identifier
        response_text: User's response text
        user_id: User's ID
        
    Returns:
        List of feedback messages
    """
    try:
        # Check cache first
        cached_feedback = FeedbackCache.get_cached_feedback(user_id, lesson_id)
        if cached_feedback:
            return [cached_feedback]

        # Get cached rules
        rules = get_feedback_rules(lesson_id)
        if not rules:
            logger.warning(f"No feedback rules found for lesson {lesson_id}")
            return ["No feedback available for this lesson."]

        feedback = []
        criteria = rules.get("criteria", {})
        response_lower = response_text.lower()

        # Enhanced keyword matching with context
        for criterion, rule_data in criteria.items():
            matches = []
            for keyword in rule_data["keywords"]:
                # Use regex for more flexible matching
                pattern = rf'\b{re.escape(keyword)}\b'
                if re.search(pattern, response_lower):
                    matches.append(keyword)

            # Dynamic threshold based on response length
            base_threshold = len(rule_data["keywords"]) * 0.3
            length_factor = min(len(response_text) / 500, 1.5)  # Adjust threshold based on response length
            threshold = base_threshold * length_factor

            # Add contextual feedback
            if len(matches) >= threshold:
                feedback.append(rule_data["good_feedback"])
                if "extra_good_feedback" in rule_data:
                    feedback.append(rule_data["extra_good_feedback"])
            else:
                feedback.append(rule_data["bad_feedback"])
                if "improvement_tips" in rule_data:
                    feedback.append(rule_data["improvement_tips"])

        # Cache the feedback
        combined_feedback = "\n\n".join(feedback)
        FeedbackCache.cache_feedback(user_id, lesson_id, combined_feedback)
        
        return feedback

    except Exception as e:
        logger.error(f"Error evaluating response for lesson {lesson_id}: {e}", exc_info=True)
        return ["An error occurred while evaluating your response. Please try again."]

def analyze_response_quality(response_text: str) -> Dict[str, Any]:
    """
    Analyze the quality of a user's response.
    
    Args:
        response_text: User's response text
        
    Returns:
        Dictionary containing quality metrics
    """
    words = response_text.split()
    return {
        'length': len(response_text),
        'word_count': len(words),
        'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
        'has_punctuation': bool(re.search(r'[.!?]', response_text)),
        'sentence_count': len(re.split(r'[.!?]+', response_text))
    }