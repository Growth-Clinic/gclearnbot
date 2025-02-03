from typing import Dict, List
from services.content_loader import content_loader

def get_lesson_structure() -> Dict[str, List[str]]:
    """
    Organizes lessons into a hierarchical structure that shows main lessons and their steps.
    
    Returns:
        A dictionary where:
        - Keys are main lesson numbers (e.g., "lesson_2")
        - Values are lists of step keys (e.g., ["lesson_2_step_1", "lesson_2_step_2"])
        
    Example:
        {
            "lesson_2": ["lesson_2_step_1", "lesson_2_step_2", "lesson_2_step_3"],
            "lesson_3": ["lesson_3_step_1", "lesson_3_step_2"]
        }
    """
    lessons = content_loader.load_content('lessons')
    lesson_structure = {}
    
    for key in lessons.keys():
        if "_step_" in key:
            main_lesson = key.split("_step_")[0]
            if main_lesson not in lesson_structure:
                lesson_structure[main_lesson] = []
            lesson_structure[main_lesson].append(key)
    
    # Sort steps within each lesson
    for main_lesson in lesson_structure:
        lesson_structure[main_lesson].sort()
    
    return lesson_structure

def is_actual_lesson(lesson_key: str) -> bool:
    """
    Determines if a lesson key represents an actual learning step.
    
    Args:
        lesson_key: The lesson identifier (e.g., "lesson_2" or "lesson_2_step_1")
        
    Returns:
        True if the lesson is a learning step, False if it's just an introduction
        
    Example:
        is_actual_lesson("lesson_2") -> False
        is_actual_lesson("lesson_2_step_1") -> True
    """
    return "_step_" in lesson_key

def get_total_lesson_steps() -> int:
    """
    Counts the total number of actual learning steps across all lessons.
    
    Returns:
        The total number of lesson steps
    """
    structure = get_lesson_structure()
    return sum(len(steps) for steps in structure.values())