import json
from pathlib import Path
from typing import Dict, Any
import logging
import os
from functools import lru_cache


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)


def validate_lessons(lessons: Dict[str, Any]) -> bool:
    required_keys = {'text', 'next'}
    return all(
        isinstance(lesson, dict) and 
        required_keys.issubset(lesson.keys())
        for lesson in lessons.values()
    )


def load_lessons() -> Dict[str, Any]:
    """
    Load lessons from a JSON file.
    
    Returns:
        Dict[str, Any]: Dictionary containing lesson data
    """
    try:
        # Get absolute path to lessons file
        base_dir = Path(__file__).resolve().parent.parent
        lessons_path = base_dir / 'data' / 'lessons.json'
        
        # Check if file exists
        if not lessons_path.exists():
            logger.error(f"Lessons file not found at {lessons_path}")
            return {}
            
        # Load and validate lessons
        with open(lessons_path, 'r', encoding='utf-8') as f:
            lessons = json.load(f)
            if not isinstance(lessons, dict):
                logger.error("Invalid lessons format: not a dictionary")
                return {}
            return lessons
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in lessons file: {e}", exc_info=True)
        return {}
    except Exception as e:
        logger.error(f"Error loading lessons: {e}", exc_info=True)
        return {}