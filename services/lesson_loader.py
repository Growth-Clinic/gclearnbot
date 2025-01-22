import json
import logging


logger = logging.getLogger(__name__)


def load_lessons():
    try:
        with open('data/lessons.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading lessons: {e}")
        return {}