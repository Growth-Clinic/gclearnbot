from functools import lru_cache
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from services.feedback_config import LESSON_FEEDBACK_RULES
from services.database import db

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

        # First check if this is a main lesson or a step
        if "_step_" not in lesson_id:
            # For main lessons (intros), just acknowledge the response
            return ["Thanks for your response! Let's continue with the lesson."]

        # Get cached rules for steps
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
    
def calculate_streak(entries: List[Dict[str, Any]]) -> int:
    """Calculate the user's current streak of consecutive days with entries."""
    if not entries:
        return 0
        
    try:
        # Sort entries by timestamp
        sorted_entries = sorted(entries, key=lambda x: x['timestamp'], reverse=True)
        
        # Get current streak
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

class LearningPatternAnalyzer:
    """Analyzes learning patterns in user responses"""
    
    # Indicators of critical thinking
    CRITICAL_THINKING_PATTERNS = {
        'analysis': [
            r'\banalyze\b', r'\bcompare\b', r'\bexamine\b', r'\bevaluate\b',
            r'\bwhy\b', r'\bhow\b', r'\brelate\b', r'\bimpact\b'
        ],
        'reasoning': [
            r'\bbecause\b', r'\btherefore\b', r'\bconsequently\b',
            r'\bthis means\b', r'\bas a result\b'
        ],
        'evidence': [
            r'\bexample\b', r'\binstance\b', r'\bcase\b', r'\bproof\b',
            r'\bdata\b', r'\bshows\b', r'\bdemonstrates\b'
        ]
    }
    
    # Indicators of concept understanding
    CONCEPT_PATTERNS = {
        'explanation': [
            r'\bmeans\b', r'\bis when\b', r'\bis about\b', r'\bdefine\b',
            r'\bconcept\b', r'\bunderstand\b'
        ],
        'application': [
            r'\bapply\b', r'\buse\b', r'\bimplement\b', r'\bpractice\b',
            r'\btry\b', r'\btest\b'
        ],
        'connection': [
            r'\bconnect\b', r'\brelate\b', r'\blink\b', r'\bsimilar\b',
            r'\bdifferent\b', r'\blike\b'
        ]
    }
    
    # Add skill patterns based on pathways
    SKILL_PATTERNS = {
        'design_thinking': [
            r'\bempathy\b', r'\buser\b', r'\bprototype\b', r'\btest\b',
            r'\bfeedback\b', r'\biterate\b', r'\bsolve\b', r'\bdesign\b'
        ],
        'business_modeling': [
            r'\bvalue\b', r'\bcustomer\b', r'\brevenue\b', r'\bmodel\b',
            r'\bmarket\b', r'\bprofit\b', r'\bcost\b', r'\bstrategy\b'
        ],
        'market_thinking': [
            r'\bscale\b', r'\bgrowth\b', r'\bchannel\b', r'\bfit\b',
            r'\buser acquisition\b', r'\bretention\b', r'\bmetrics\b'
        ],
        'user_thinking': [
            r'\bbehavior\b', r'\bemotion\b', r'\bjourney\b', r'\bexperience\b',
            r'\bpersona\b', r'\bneed\b', r'\bwant\b', r'\bfeeling\b'
        ],
        'agile_thinking': [
            r'\bsprint\b', r'\biterate\b', r'\bscrum\b', r'\bbacklog\b',
            r'\bprioritize\b', r'\btask\b', r'\bresource\b', r'\bplan\b'
        ]
    }
    
    @classmethod
    def analyze_learning_patterns(cls, response_text: str) -> Dict[str, Any]:
        """Analyze response for learning patterns."""
        text = response_text.lower()
        
        # Analyze critical thinking patterns
        critical_thinking = {
            category: sum(1 for pattern in patterns if re.search(pattern, text))
            for category, patterns in cls.CRITICAL_THINKING_PATTERNS.items()
        }
        
        # Analyze concept understanding patterns
        concept_understanding = {
            category: sum(1 for pattern in patterns if re.search(pattern, text))
            for category, patterns in cls.CONCEPT_PATTERNS.items()
        }
        
        # Calculate overall scores (0-100)
        ct_score = min(100, sum(critical_thinking.values()) * 20)
        cu_score = min(100, sum(concept_understanding.values()) * 20)
        
        return {
            'critical_thinking': {
                'score': ct_score,
                'patterns': critical_thinking
            },
            'concept_understanding': {
                'score': cu_score,
                'patterns': concept_understanding
            },
            'learning_style': cls._determine_learning_style(critical_thinking, concept_understanding)
        }
    
    @classmethod
    def analyze_skills(cls, response_text: str) -> Dict[str, Any]:
        """Analyze response for skill indicators."""
        text = response_text.lower()
        
        # Track skills found in response
        skills = {}
        for skill_area, patterns in cls.SKILL_PATTERNS.items():
            matches = [pattern for pattern in patterns if re.search(pattern, text)]
            if matches:
                # Calculate skill score (0-100)
                score = min(100, (len(matches) / len(patterns)) * 100)
                skills[skill_area] = {
                    'score': score,
                    'indicators': matches
                }
        
        return skills
    
    @staticmethod
    def _determine_learning_style(ct_patterns: Dict[str, int], 
                                cu_patterns: Dict[str, int]) -> str:
        """Determine the user's learning style based on pattern analysis."""
        if ct_patterns['analysis'] > cu_patterns['explanation']:
            return 'analytical'
        elif cu_patterns['application'] > ct_patterns['evidence']:
            return 'practical'
        elif ct_patterns['reasoning'] > cu_patterns['connection']:
            return 'logical'
        else:
            return 'balanced'


def analyze_response_quality(response_text: str) -> Dict[str, Any]:
    """
    Analyze the quality of a user's response.
    
    Args:
        response_text: User's response text
        
    Returns:
        Dictionary containing quality metrics
    """
    try:
        # Basic text cleanup
        clean_text = response_text.strip()
        words = clean_text.split()
        sentences = re.split(r'[.!?]+', clean_text)
        
        # Core metrics
        metrics = {
            'length': len(clean_text),
            'word_count': len(words),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'has_punctuation': bool(re.search(r'[.!?]', clean_text)),
            'includes_details': len(words) > 30
        }

        #Add learning pattern analysis
        pattern_analysis = LearningPatternAnalyzer.analyze_learning_patterns(clean_text)
        metrics.update(pattern_analysis)

        # Add skill analysis
        skill_analysis = LearningPatternAnalyzer.analyze_skills(clean_text)
        metrics['skills'] = skill_analysis
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error analyzing response quality: {e}")
        return {
            'length': len(response_text),
            'word_count': len(response_text.split()),
            'error': str(e)
        }


def format_feedback_message(feedback_list: List[str], quality_metrics: Dict[str, Any]) -> str:
    """
    Format feedback into an engaging, well-structured message.
    
    Args:
        feedback_list: List of feedback messages
        quality_metrics: Dictionary containing response quality metrics
        
    Returns:
        Formatted feedback message with emojis and markdown
    """
    message = "📝 *Response Analysis*\n\n"
    
    # Add quality indicators
    if quality_metrics.get('includes_details'):
        message += "✨ *Detailed Response!* Good level of explanation.\n"
    if quality_metrics.get('has_punctuation'):
        message += "📖 *Well Structured!* Good use of punctuation.\n"
    
    # Add main feedback from lesson
    message += "\n*Feedback:*\n" + "\n".join(feedback_list)

    #Add learning pattern insights if available
    if 'critical_thinking' in quality_metrics:
        ct_score = quality_metrics['critical_thinking']['score']
        message += f"\n\n🧠 *Thinking Patterns:*\n"
        message += f"• Critical Thinking: {ct_score}/100\n"
        
        if ct_score > 80:
            message += "Excellent analytical thinking!\n"
        elif ct_score > 60:
            message += "Good critical analysis. Try adding more supporting evidence.\n"
        elif ct_score > 40:
            message += "Consider explaining your reasoning more deeply.\n"
    
    if 'concept_understanding' in quality_metrics:
        cu_score = quality_metrics['concept_understanding']['score']
        message += f"\n📚 *Concept Understanding:*\n"
        message += f"• Understanding Score: {cu_score}/100\n"
        
        learning_style = quality_metrics.get('learning_style', 'balanced')
        message += f"• Learning Style: {learning_style.title()}\n"
    
    # Add basic stats
    message += f"\n\n📊 *Response Stats:*\n"
    message += f"• Words: {quality_metrics['word_count']}\n"
    message += f"• Sentences: {quality_metrics['sentence_count']}\n"
    
    return message