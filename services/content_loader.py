import json
from pathlib import Path
from typing import Dict, Any
import logging
import os
from functools import lru_cache


logger = logging.getLogger(__name__)


class ContentLoader:
    """Handles loading of various content types (lessons, tasks, guides, pathways)"""
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.data_dir = self.base_dir / 'data'

    @lru_cache(maxsize=1)
    def load_content(self, content_type: str) -> Dict[str, Any]:
        """
        Load content from JSON files with detailed error checking.
        """
        try:
            file_path = self.data_dir / f"{content_type}.json"
            
            if not file_path.exists():
                logger.error(f"{content_type} file not found at {file_path}")
                return {}
                
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
                logger.info(f"Raw content from {content_type}.json: {raw_content[:200]}...")
                
                content = json.loads(raw_content)
                logger.info(f"Parsed {content_type} structure: {list(content.keys()) if isinstance(content, dict) else 'not a dict'}")
                
                # Return the full content instead of trying to get inner content
                return content
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {content_type} file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading {content_type}: {e}")
            return {}

    def get_all_tasks(self) -> Dict[str, Any]:
        """Get all available tasks, regardless of type"""
        content = self.load_content('tasks')
        tasks_dict = content.get('tasks', {})

        if not tasks_dict:
            logger.warning("No tasks found in tasks.json")
            return {}

        logger.info(f"Total tasks found: {len(tasks_dict)}")
        return tasks_dict


    def get_full_lessons(self) -> Dict[str, Any]:
        """Get main lessons (not steps)"""
        lessons = self.load_content('lessons')
        return {
            lesson_id: lesson for lesson_id, lesson in lessons.items()
            if not '_step_' in lesson_id
        }

    def get_lesson_steps(self, lesson_id: str) -> Dict[str, Any]:
        """Get all steps for a specific lesson"""
        lessons = self.load_content('lessons')
        return {
            step_id: step for step_id, step in lessons.items()
            if step_id.startswith(f"{lesson_id}_step_")
        }

    def get_related_content(self, content_id: str, content_type: str) -> Dict[str, Any]:
        """
        Get related content for a specific item.
        
        Args:
            content_id: ID of the content item
            content_type: Type of the content ('lessons', 'tasks', 'guides')
            
        Returns:
            Dictionary with related content
        """
        content = self.load_content(content_type)
        item = content.get(content_id, {})
        
        related = {
            'tasks': [],
            'guides': [],
            'pathways': []
        }
        
        # Get related tasks
        if 'related_tasks' in item:
            tasks = self.load_content('tasks')
            related['tasks'] = [
                tasks[task_id] for task_id in item['related_tasks']
                if task_id in tasks
            ]
            
        # Get related guides
        if 'related_guides' in item:
            guides = self.load_content('guides')
            related['guides'] = [
                guides[guide_id] for guide_id in item['related_guides']
                if guide_id in guides
            ]
            
        # Get related pathways
        if 'pathways' in item:
            pathways = self.load_content('pathways')
            related['pathways'] = [
                pathways[pathway_id] for pathway_id in item['pathways']
                if pathway_id in pathways
            ]
            
        return related
    
    def validate_content_structure(self) -> None:
        """Validate the structure of loaded content files and log any issues"""
        content = self.load_content('tasks')
        logger.info("Validating content structure...")
        
        if not isinstance(content, dict):
            logger.error(f"Tasks content is not a dictionary: {type(content)}")
            return
            
        tasks_dict = content.get('tasks', {})
        if not tasks_dict:
            logger.error("No tasks found in content")
            return
        
        quick_tasks_count = sum(1 for task in tasks_dict.values() 
                              if isinstance(task, dict) and task.get('type') == 'quick_task')
        logger.info(f"Found {quick_tasks_count} quick tasks in content")

# Create a singleton instance
content_loader = ContentLoader()