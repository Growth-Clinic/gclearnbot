import logging

logger = logging.getLogger(__name__)

FEEDBACK_TEMPLATES = {
    "strength_template": "Based on your responses, you consistently show strength in {strength_area}. For example, in your {previous_lesson} response, you {strength_example}.",
    
    "improvement_template": "I notice you sometimes struggle with {weakness_area}. In {previous_lesson}, you could have {improvement_suggestion}. Let's focus on this in upcoming lessons.",
    
    "progress_template": "You've made significant progress with {skill_area} since {first_lesson}. Initially, you {initial_approach}, but now you're {current_approach}.",
    
    "connection_template": "This reminds me of your thoughts in {related_lesson} where you {previous_insight}. How might those insights apply here?",
    
    "streak_template": "You've maintained consistent quality in {quality_aspect} for {streak_count} responses! Keep up the excellent work.",
}

# Helper functions for template processing
def format_template(template_key: str, **kwargs) -> str:
    """Format a feedback template with provided variables."""
    template = FEEDBACK_TEMPLATES.get(template_key)
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing template variable: {e}")
        return template  # Return unformatted template as fallback

def get_template_variables(template_key: str) -> list:
    """Get required variables for a template."""
    template = FEEDBACK_TEMPLATES.get(template_key)
    if not template:
        return []
    # Extract variables between curly braces
    import re
    return re.findall(r'\{(\w+)\}', template)