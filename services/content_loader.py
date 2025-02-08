"""
Content loader for bot resources.

Note: Task processing is temporarily disabled. To re-enable:
1. Uncomment original get_all_tasks() code below
2. Remove temporary return {}
3. Uncomment original handle_start_choice() code in user_handlers.py
4. Restart the bot
"""

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
        
    def format_for_platform(self, content: Dict[str, Any], platform: str = 'telegram') -> Dict[str, Any]:
        """Format content based on platform requirements."""
        if not content:
            return {}

        try:
            if platform == 'slack':
                return self._format_for_slack(content)
            return self._format_for_telegram(content)  # Default to Telegram formatting
            
        except Exception as e:
            logger.error(f"Error formatting content for {platform}: {e}")
            return content  # Return original content on error

    def _format_for_slack(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Format content specifically for Slack."""
        formatted = content.copy()
        
        # Convert Telegram markdown to Slack mrkdwn
        if 'text' in formatted:
            text = formatted['text']
            # Convert Telegram markdown to Slack mrkdwn
            text = text.replace('*', '*')  # Bold remains the same
            text = text.replace('_', '_')  # Italic remains the same
            text = text.replace('`', '`')  # Code remains the same
            text = text.replace('\n', '\n')  # Newlines remain the same
            formatted['text'] = text
            
            # Add Slack-specific blocks if needed
            formatted['blocks'] = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }]
            
            # Add button if 'next' is present
            if 'next' in formatted:
                formatted['blocks'].append({
                    "type": "actions",
                    "elements": [{
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Continue"
                        },
                        "value": formatted['next'],
                        "action_id": f"lesson_next_{formatted['next']}"
                    }]
                })
        
        return formatted

    def _format_for_telegram(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Format content specifically for Telegram (maintains existing format)."""
        return content  # Current format is already Telegram-compatible

    def get_all_tasks(self) -> Dict[str, Any]:
        """Get all available tasks, regardless of type"""
        # Temporarily return empty dict to disable task loading
        return {}
        
        # Original code commented out but preserved for easy re-enabling
        '''
        content = self.load_content('tasks')
        tasks_dict = content.get('tasks', {})

        if not tasks_dict:
            logger.warning("No tasks found in tasks.json")
            return {}

        logger.info(f"Total tasks found: {len(tasks_dict)}")
        return tasks_dict
        '''


    def get_full_lessons(self, platform: str = 'telegram') -> Dict[str, Any]:
        """Get main lessons (not steps) formatted for specified platform."""
        lessons = self.load_content('lessons')
        full_lessons = {
            lesson_id: lesson for lesson_id, lesson in lessons.items()
            if not '_step_' in lesson_id
        }
        return self.format_for_platform(full_lessons, platform)

    def get_lesson_steps(self, lesson_id: str, platform: str = 'telegram') -> Dict[str, Any]:
        """Get all steps for a specific lesson formatted for specified platform."""
        lessons = self.load_content('lessons')
        steps = {
            step_id: step for step_id, step in lessons.items()
            if step_id.startswith(f"{lesson_id}_step_")
        }
        return self.format_for_platform(steps, platform)

    def get_related_content(self, content_id: str, content_type: str, platform: str = 'telegram') -> Dict[str, Any]:
        """Get related content formatted for specified platform."""
        content = self.load_content(content_type)
        item = content.get(content_id, {})
        
        related = {
            'tasks': [],
            'guides': [],
            'pathways': []
        }
        
        # Get related content
        if 'related_tasks' in item:
            tasks = self.load_content('tasks')
            related['tasks'] = [
                tasks[task_id] for task_id in item['related_tasks']
                if task_id in tasks
            ]
            
        if 'related_guides' in item:
            guides = self.load_content('guides')
            related['guides'] = [
                guides[guide_id] for guide_id in item['related_guides']
                if guide_id in guides
            ]
            
        if 'pathways' in item:
            pathways = self.load_content('pathways')
            related['pathways'] = [
                pathways[pathway_id] for pathway_id in item['pathways']
                if pathway_id in pathways
            ]
            
        return self.format_for_platform(related, platform)

    def validate_content_structure(self) -> None:
        """Validate the structure of loaded content files and log any issues."""
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