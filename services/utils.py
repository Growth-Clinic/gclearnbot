import re
from typing import List
from services.feedback_config import LESSON_FEEDBACK_RULES
from werkzeug.security import check_password_hash

def extract_keywords_from_response(response: str, lesson_id: str) -> list:
    """
    Extract keywords from the user's response based on the lesson's feedback rules.

    Args:
        response (str): The user's response.
        lesson_id (str): The ID of the current lesson.

    Returns:
        list: A list of keywords found in the response.
    """
    if lesson_id not in LESSON_FEEDBACK_RULES:
        return []
    
    # Get the keywords for the current lesson
    criteria = LESSON_FEEDBACK_RULES[lesson_id]["criteria"]
    keywords = set()
    
    for criterion, rules in criteria.items():
        keywords.update(rules["keywords"])
    
    # Find keywords in the response
    found_keywords = [kw for kw in keywords if kw.lower() in response.lower()]
    return found_keywords


def verify_password(plain_password, hashed_password):
    """Compare hashed password with plain password"""
    return check_password_hash(hashed_password, plain_password)