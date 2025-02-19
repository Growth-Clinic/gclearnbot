"""
Enhanced Feedback and Skill Analysis System

This module provides comprehensive feedback and skill analysis for the learning platform.
It combines traditional feedback mechanisms with advanced skill tracking and progression analysis.

Key Components:
- Feedback caching and rules management
- Learning pattern analysis (critical thinking, concept understanding)
- Skill progression tracking across multiple pathways
- Level-based skill assessment (beginner, intermediate, advanced)
- Comprehensive feedback formatting with progress insights

Usage:
    # Analyze a user response
    metrics = analyze_response_quality(response_text)
    
    # Generate feedback
    feedback = await format_feedback_message(feedback_list, metrics, user_id)
    
    # Track skill progression
    await SkillProgressTracker.update_skill_progress(user_id, skill_scores)

Database Collections:
    - user_skills: Stores user skill progression and history
    - feedback: Stores cached feedback
    - feedback_analytics: Stores analytics data

Version: 2.0.0
Last Updated: February 2025
"""

from functools import lru_cache
import re
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
import logging
import math
import warnings
from collections import Counter
from services.feedback_config import LESSON_FEEDBACK_RULES
from services.database import db
from services.learning_insights import LearningInsightsManager
from nltk.stem import PorterStemmer
from nltk.corpus import wordnet
import nltk

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

# Initialize NLTK data
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')

class DynamicSkillAnalyzer:
    """
    Analyzes user responses dynamically to identify skills and learning patterns
    without relying on predefined lesson mappings.
    """

    def __init__(self):
        """Initialize with stemming capability"""
        self.stemmer = PorterStemmer()
        
    def _get_synonyms(self, word: str) -> Set[str]:
        """Get synonyms for a word using WordNet."""
        synonyms = set()
        for syn in wordnet.synsets(word):
            for lemma in syn.lemmas():
                synonyms.add(lemma.name().lower())
        return synonyms

    def _check_pattern_match(self, text: str, pattern: str) -> bool:
        """Enhanced pattern matching using stems and synonyms."""
        text_lower = text.lower()
        pattern_lower = pattern.lower()
        
        # Direct match
        if pattern_lower in text_lower:
            return True
            
        # Stem match
        text_stems = {self.stemmer.stem(word) for word in text_lower.split()}
        pattern_stem = self.stemmer.stem(pattern_lower)
        if pattern_stem in text_stems:
            return True
            
        # Synonym match
        pattern_synonyms = self._get_synonyms(pattern_lower)
        return any(syn in text_lower for syn in pattern_synonyms)
    
    # Core skill indicators that can be detected from language patterns
    SKILL_INDICATORS = {
        'analytical_thinking': {
            'patterns': [
                r'because', r'therefore', r'consequently', r'analyze', 
                r'compare', r'evaluate', r'conclude', r'investigate'
            ],
            'weight': 1.2  # Higher weight for important skills
        },
        'problem_solving': {
            'patterns': [
                r'solve', r'solution', r'approach', r'method', 
                r'strategy', r'tackle', r'handle', r'resolve'
            ],
            'weight': 1.2
        },
        'creativity': {
            'patterns': [
                r'create', r'design', r'innovative', r'novel',
                r'unique', r'original', r'imagine', r'develop'
            ],
            'weight': 1.1
        },
        'communication': {
            'patterns': [
                r'explain', r'describe', r'articulate', r'convey',
                r'express', r'present', r'share', r'discuss'
            ],
            'weight': 1.0
        },
        'research': {
            'patterns': [
                r'research', r'investigate', r'study', r'explore',
                r'examine', r'analyze', r'review', r'understand'
            ],
            'weight': 1.0
        }
    }
    
    # Contextual indicators that suggest skill application
    CONTEXT_INDICATORS = {
        'real_world_application': [
            r'in practice', r'real.world', r'applied', r'implemented',
            r'used.in', r'practical', r'actually', r'experience'
        ],
        'depth_of_understanding': [
            r'deeper', r'underlying', r'fundamental', r'core',
            r'essential', r'key', r'critical', r'important'
        ],
        'learning_progression': [
            r'learned', r'improved', r'better.understanding',
            r'now.i.can', r'progress', r'growth', r'development'
        ]
    }

    @classmethod
    def analyze_response(self, response_text: str) -> Dict[str, Any]:
        """Analyzes a response with enhanced pattern matching."""
        text = response_text.lower()
        
        # Analyze core skills with enhanced matching
        skills = {}
        for skill, config in self.SKILL_INDICATORS.items():
            matches = sum(1 for pattern in config['patterns'] 
                         if self._check_pattern_match(text, pattern))
            if matches:
                base_score = min(100, (matches / len(config['patterns'])) * 100)
                weighted_score = base_score * config['weight']
                skills[skill] = {
                    'score': round(weighted_score, 2),
                    'matches': matches,
                    'level': self._determine_skill_level(weighted_score)
                }
        
        # Analyze contextual application
        context_scores = {}
        for context, patterns in self.CONTEXT_INDICATORS.items():
            matches = sum(1 for pattern in patterns if re.search(pattern, text))
            if matches:
                context_scores[context] = min(100, (matches / len(patterns)) * 100)
        
        return {
            'skills': skills,
            'context': context_scores,
            'overall_score': self._calculate_overall_score(skills, context_scores)
        }

    @classmethod
    def _determine_skill_level(cls, score: float) -> str:
        """Determine skill level based on score."""
        if isinstance(score, (int, float)):
            if score >= 80:
                return 'advanced'
            elif score >= 60:
                return 'intermediate'
            return 'beginner'
        return 'beginner'  # Default if score is invalid

    @staticmethod
    def _calculate_overall_score(skills: Dict[str, Any], 
                               context: Dict[str, float]) -> float:
        """Calculate overall skill application score."""
        if not skills:
            return 0.0
            
        skill_avg = sum(s['score'] for s in skills.values()) / len(skills)
        context_avg = (sum(context.values()) / len(context)) if context else 0
        
        # Weight skill scores higher than context
        return round((skill_avg * 0.7 + context_avg * 0.3), 2)

class LearningTrajectoryAnalyzer:
    """
    Analyzes learning trajectories and patterns across multiple responses.
    """
    
    def __init__(self):
        self.topic_clusters = {
            'technical': [
                'code', 'programming', 'software', 'data', 'algorithm',
                'system', 'technical', 'development', 'engineering'
            ],
            'business': [
                'strategy', 'business', 'market', 'customer', 'revenue',
                'product', 'service', 'value', 'growth'
            ],
            'design': [
                'design', 'user', 'interface', 'experience', 'prototype',
                'visual', 'creative', 'aesthetic', 'usability'
            ],
            'leadership': [
                'lead', 'team', 'manage', 'coordinate', 'organize',
                'direct', 'guide', 'mentor', 'facilitate'
            ]
        }

    def analyze_trajectory(self, responses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze learning trajectory from a series of responses.
        """
        if not responses:
            return {}
            
        try:
            # Sort responses by timestamp
            sorted_responses = sorted(responses, 
                                   key=lambda x: x['timestamp'])
            
            # Analyze topic progression
            topic_progression = self._analyze_topic_progression(sorted_responses)
            
            # Analyze complexity progression
            complexity_scores = self._analyze_complexity_progression(sorted_responses)
            
            # Identify knowledge gaps
            knowledge_gaps = self._identify_knowledge_gaps(sorted_responses)
            
            # Calculate learning velocity
            velocity = self._calculate_learning_velocity(sorted_responses)
            
            return {
                'topic_progression': topic_progression,
                'complexity_progression': complexity_scores,
                'knowledge_gaps': knowledge_gaps,
                'learning_velocity': velocity
            }
            
        except Exception as e:
            logger.error(f"Error analyzing learning trajectory: {e}")
            return {}

    def _analyze_topic_progression(self, responses: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """Analyze how topic focus changes over time."""
        progression = {topic: [] for topic in self.topic_clusters}
        
        for response in responses:
            text = response['response'].lower()
            for topic, keywords in self.topic_clusters.items():
                # Calculate topic relevance score
                matches = sum(1 for kw in keywords if kw in text)
                score = min(100, (matches / len(keywords)) * 100)
                progression[topic].append(score)
        
        return progression

    def _analyze_complexity_progression(self, responses: List[Dict[str, Any]]) -> List[float]:
        """Analyze how response complexity changes over time."""
        complexity_scores = []
        
        for response in responses:
            text = response['response']
            
            # Calculate complexity score based on multiple factors
            words = text.split()
            unique_words = len(set(words))
            avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
            
            # Complex sentence indicators
            complex_indicators = sum(1 for pattern in [
                r'because', r'therefore', r'however', r'although',
                r'nevertheless', r'furthermore', r'consequently'
            ] if re.search(pattern, text.lower()))
            
            # Combine factors into complexity score
            complexity = (
                (unique_words / len(words) if words else 0) * 40 +  # Vocabulary diversity
                min(avg_word_length * 10, 30) +                     # Word sophistication
                min(complex_indicators * 10, 30)                    # Structural complexity
            )
            
            complexity_scores.append(min(100, complexity))
        
        return complexity_scores

    def _identify_knowledge_gaps(self, responses: List[Dict[str, Any]]) -> List[str]:
        """Identify potential knowledge gaps from response patterns."""
        gaps = []
        
        # Combine all responses
        all_text = ' '.join(r['response'].lower() for r in responses)
        
        # Check for uncertainty indicators
        uncertainty_patterns = [
            (r'not.sure.about', 'conceptual understanding'),
            (r'confused.by', 'clarity'),
            (r'difficult.to.understand', 'comprehension'),
            (r'need.help.with', 'skill application'),
            (r'unclear', 'concept clarity')
        ]
        
        for pattern, gap_type in uncertainty_patterns:
            if re.search(pattern, all_text):
                gaps.append(gap_type)
        
        return gaps

    def _calculate_learning_velocity(self, responses: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate the rate of learning progress."""
        if len(responses) < 2:
            return {'velocity': 0, 'acceleration': 0}
            
        # Calculate complexity scores over time
        complexity_scores = self._analyze_complexity_progression(responses)
        
        # Calculate velocity (change in complexity over time)
        time_periods = len(complexity_scores) - 1
        velocity = (complexity_scores[-1] - complexity_scores[0]) / time_periods
        
        # Calculate acceleration (change in velocity)
        if len(complexity_scores) > 2:
            first_half = (complexity_scores[time_periods//2] - complexity_scores[0]) / (time_periods//2)
            second_half = (complexity_scores[-1] - complexity_scores[time_periods//2]) / (time_periods - time_periods//2)
            acceleration = second_half - first_half
        else:
            acceleration = 0
            
        return {
            'velocity': round(velocity, 2),
            'acceleration': round(acceleration, 2)
        }

class SemanticAnalyzer:
    """
    Performs semantic analysis on user responses to understand meaning and context.
    """
    
    def __init__(self):
        self.semantic_markers = {
            'understanding': [
                (r'i.understand', 1.0),
                (r'now.i.see', 1.0),
                (r'makes.sense', 0.8),
                (r'i.learned', 0.9)
            ],
            'application': [
                (r'i.applied', 1.0),
                (r'i.tried', 0.8),
                (r'in.practice', 0.9),
                (r'when.i.used', 0.9)
            ],
            'synthesis': [
                (r'combining', 1.0),
                (r'connecting', 0.9),
                (r'relating.to', 0.8),
                (r'integrating', 1.0)
            ],
            'evaluation': [
                (r'i.think', 0.7),
                (r'in.my.opinion', 0.8),
                (r'i.believe', 0.7),
                (r'analyzing', 0.9)
            ]
        }

    def analyze_response(self, text: str) -> Dict[str, Any]:
        """
        Perform semantic analysis on a response.
        """
        text = text.lower()
        
        # Analyze semantic markers
        semantic_scores = {}
        for category, markers in self.semantic_markers.items():
            matches = []
            for pattern, weight in markers:
                if re.search(pattern, text):
                    matches.append(weight)
            
            if matches:
                semantic_scores[category] = round(sum(matches) / len(markers) * 100, 2)
        
        # Analyze semantic coherence
        coherence_score = self._analyze_coherence(text)
        
        # Analyze conceptual depth
        depth_score = self._analyze_depth(text)
        
        return {
            'semantic_categories': semantic_scores,
            'coherence': coherence_score,
            'depth': depth_score,
            'overall_understanding': self._calculate_understanding_score(
                semantic_scores, coherence_score, depth_score
            )
        }

    def _analyze_coherence(self, text: str) -> float:
        """Analyze the coherence of the response."""
        # Check for logical connectors
        connectors = [
            'because', 'therefore', 'however', 'although',
            'furthermore', 'moreover', 'consequently', 'thus'
        ]
        
        connector_count = sum(1 for c in connectors if c in text)
        
        # Check for paragraph structure
        has_paragraphs = len(text.split('\n\n')) > 1
        
        # Check for topic consistency
        sentences = text.split('.')
        word_sets = [set(s.split()) for s in sentences if s.strip()]
        
        # Calculate overlap between adjacent sentences
        overlaps = []
        for i in range(len(word_sets) - 1):
            overlap = len(word_sets[i] & word_sets[i + 1]) / len(word_sets[i] | word_sets[i + 1])
            overlaps.append(overlap)
        
        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
        
        # Combine factors
        coherence_score = (
            min(connector_count * 10, 40) +  # Logical connection (40%)
            (30 if has_paragraphs else 0) +  # Structure (30%)
            avg_overlap * 30                 # Topic consistency (30%)
        )
        
        return min(100, coherence_score)

    def _analyze_depth(self, text: str) -> float:
        """Analyze the conceptual depth of the response."""
        # Check for explanation patterns
        explanation_patterns = [
            (r'because', 10),
            (r'means.that', 8),
            (r'in.other.words', 8),
            (r'for.example', 7),
            (r'specifically', 9)
        ]
        
        explanation_score = sum(weight for pattern, weight in explanation_patterns 
                              if re.search(pattern, text))
        
        # Check for conceptual vocabulary
        concept_indicators = [
            'concept', 'principle', 'theory', 'framework',
            'approach', 'methodology', 'system', 'process'
        ]
        
        concept_score = sum(10 for word in concept_indicators if word in text)
        
        # Calculate final depth score
        depth_score = (
            min(explanation_score, 60) +  # Explanation quality (60%)
            min(concept_score, 40)        # Conceptual vocabulary (40%)
        )
        
        return min(100, depth_score)
    

    def _calculate_understanding_score(self, semantic_scores: Dict[str, float],
                                    coherence_score: float, depth_score: float) -> float:
        """Calculate overall understanding score."""
        if not semantic_scores:
            return 0.0
        
        # Weighted average of semantic categories
        semantic_avg = sum(semantic_scores.values()) / len(semantic_scores)

        # Combine semantic analysis with coherence and depth
        overall_score = (
            semantic_avg * 0.5 +  # Semantic categories (50%)
            coherence_score * 0.3 +  # Coherence (30%)
            depth_score * 0.2        # Depth (20%)
        )
        
        return round(overall_score, 2)


class FeedbackCache:
    """Manages caching of user responses and feedback intelligently"""
    _cache = {}
    _cache_timeout = timedelta(minutes=30)

    @classmethod
    def get_cached_feedback(cls, user_id: int, lesson_id: str, response_text: str) -> Optional[str]:
        """Only return cached feedback if the response hasn't changed"""
        cache_key = f"{user_id}_{lesson_id}"
        cached_data = cls._cache.get(cache_key)

        if cached_data:
            if cached_data["response_text"] == response_text:  # Only use cache if response is identical
                return cached_data["feedback"]
            else:
                del cls._cache[cache_key]  # Invalidate old feedback if the response changes

        return None

    @classmethod
    def cache_feedback(cls, user_id: int, lesson_id: str, response_text: str, feedback: str) -> None:
        """Cache feedback but only for the same response"""
        cache_key = f"{user_id}_{lesson_id}"
        cls._cache[cache_key] = {
            "feedback": feedback,
            "response_text": response_text,  # Store response to detect changes
            "timestamp": datetime.now()
        }

# Add new class for skill tracking configuration
class SkillConfig:
    """
    Manages skill patterns and progression tracking across learning pathways.
    
    This class defines the patterns and progression metrics for each skill area,
    providing a structured approach to skill assessment and level determination.
    
    Key Features:
        - Defined patterns for each learning pathway
        - Level-based skill progression (beginner, intermediate, advanced)
        - Pattern matching for skill detection
        - Progression thresholds and metrics
        
    Skill Areas:
        - Design Thinking: User research, prototyping, iteration
        - Business Modeling: Value proposition, revenue models, strategy
        - Market Thinking: Growth, channels, metrics
        - User Thinking: Behavior analysis, empathy, research
        - Agile Thinking: Sprint planning, iteration, reviews
        
    Levels:
        - Beginner: Basic concept understanding and application
        - Intermediate: Advanced concept usage and integration
        - Advanced: Mastery and innovative application
        
    Usage:
        patterns = SkillConfig.get_skill_patterns('design_thinking')
        level = SkillConfig.determine_skill_level('market_thinking', score)
    """
    
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
    
    # Base patterns for different skill areas
    SKILL_PATTERNS = {
        'design_thinking': {
            'patterns': [
                r'\bempathy\b', r'\buser\b', r'\bprototype\b', r'\btest\b',
                r'\bfeedback\b', r'\biterate\b', r'\bsolve\b', r'\bdesign\b'
            ],
            'levels': {
                'beginner': ['empathy', 'user', 'test'],
                'intermediate': ['prototype', 'feedback', 'iterate'],
                'advanced': ['solve', 'design']
            }
        },
        'business_modeling': {
            'patterns': [
                r'\bvalue\b', r'\bcustomer\b', r'\brevenue\b', r'\bmodel\b',
                r'\bmarket\b', r'\bprofit\b', r'\bcost\b', r'\bstrategy\b'
            ],
            'levels': {
                'beginner': ['value', 'customer', 'market'],
                'intermediate': ['revenue', 'cost', 'model'],
                'advanced': ['profit', 'strategy']
            }
        },
        'market_thinking': {
            'patterns': [
                r'\bscale\b', r'\bgrowth\b', r'\bchannel\b', r'\bfit\b',
                r'\buser acquisition\b', r'\bretention\b', r'\bmetrics\b'
            ],
            'levels': {
                'beginner': ['channel', 'fit', 'metrics'],
                'intermediate': ['growth', 'retention'],
                'advanced': ['scale', 'user acquisition']
            }
        },
        'user_thinking': {
            'patterns': [
                r'\bbehavior\b', r'\bemotion\b', r'\bjourney\b', r'\bexperience\b',
                r'\bpersona\b', r'\bneed\b', r'\bwant\b', r'\bfeeling\b',
                r'\buser research\b', r'\binterview\b', r'\bempathy\b'
            ],
            'levels': {
                'beginner': ['need', 'want', 'feeling', 'emotion'],
                'intermediate': ['behavior', 'journey', 'experience'],
                'advanced': ['persona', 'user research', 'empathy']
            }
        },
        'agile_thinking': {
            'patterns': [
                r'\bsprint\b', r'\biterate\b', r'\bscrum\b', r'\bbacklog\b',
                r'\bprioritize\b', r'\btask\b', r'\bresource\b', r'\bplan\b',
                r'\bdeliver\b', r'\breview\b', r'\bretrospective\b'
            ],
            'levels': {
                'beginner': ['task', 'plan', 'resource'],
                'intermediate': ['sprint', 'backlog', 'prioritize'],
                'advanced': ['iterate', 'review', 'retrospective']
            }
        }
    }

    # Common progression metrics for all skills
    DEFAULT_PROGRESSION_METRICS = {
        'responses_needed': 5,
        'threshold_scores': {
            'beginner': 30,
            'intermediate': 60,
            'advanced': 80
        }
    }

    @classmethod
    def validate_patterns(cls) -> bool:
        """
        Validate all skill patterns during initialization.
        Returns True if valid, logs errors and returns False if invalid.
        """
        try:
            for skill_area, config in cls.SKILL_PATTERNS.items():
                # Check required keys
                if not all(key in config for key in ['patterns', 'levels']):
                    logger.error(f"Missing required keys in {skill_area} configuration")
                    return False
                
                # Validate patterns
                if not config['patterns'] or not all(isinstance(p, str) for p in config['patterns']):
                    logger.error(f"Invalid patterns in {skill_area} configuration")
                    return False
                
                # Validate levels
                levels = config['levels']
                if not isinstance(levels, dict) or not all(k in levels for k in ['beginner', 'intermediate', 'advanced']):
                    logger.error(f"Invalid level configuration in {skill_area}")
                    return False
                
                # Validate keywords in levels exist in patterns
                pattern_keywords = set(re.sub(r'\b|\\', '', p) for p in config['patterns'])
                for level_keywords in levels.values():
                    if not all(kw in pattern_keywords for kw in level_keywords):
                        logger.error(f"Level keywords not found in patterns for {skill_area}")
                        return False
            
            logger.info("All skill patterns validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error validating skill patterns: {e}")
            return False

    @classmethod
    def get_skill_patterns(cls, skill_area: str) -> Dict[str, Any]:
        """Get patterns and progression metrics for a skill area"""
        # Add validation check
        if not hasattr(cls, '_patterns_validated'):
            cls._patterns_validated = cls.validate_patterns()
            if not cls._patterns_validated:
                logger.warning("Skill patterns validation failed")

        patterns = cls.SKILL_PATTERNS.get(skill_area, {})
        if patterns:
            patterns['progression_metrics'] = cls.DEFAULT_PROGRESSION_METRICS
        return patterns

    @classmethod
    def determine_skill_level(cls, skill_area: str, score: float) -> str:
        """Determine skill level based on score"""
        thresholds = cls.DEFAULT_PROGRESSION_METRICS['threshold_scores']
        
        if score >= thresholds['advanced']:
            return 'advanced'
        elif score >= thresholds['intermediate']:
            return 'intermediate'
        return 'beginner'

class SkillProgressTracker:
    """
    Tracks and manages user skill progression over time.
    
    This class handles the storage and retrieval of skill progression data,
    maintaining a history of user performance and skill levels across different
    learning pathways.
    
    Features:
        - Historical tracking of skill scores
        - Level progression monitoring
        - Highest score tracking
        - Recent performance analysis
        
    Database Schema:
        user_skills: {
            user_id: int,
            skills: {
                skill_area: {
                    level: str,
                    recent_scores: List[float],
                    highest_score: float
                }
            }
        }
        
    Usage:
        # Update skill progress
        await SkillProgressTracker.update_skill_progress(user_id, skill_scores)
        
        # Get current progress
        progress = await SkillProgressTracker.get_skill_progress(user_id)
    
    Note:
        Maintains the last 5 scores for trend analysis and level determination.
        Level changes are determined by average performance over recent attempts.
    """
    
    @staticmethod
    async def update_skill_progress(user_id: int, skill_scores: Dict[str, Any]) -> None:
        """Update user's skill progress in the database"""
        try:
            # Get user's current skill progress
            user_skills = await db.user_skills.find_one({'user_id': user_id}) or {
                'user_id': user_id,
                'skills': {}
            }
            
            # Update skills with new scores
            for skill_area, data in skill_scores.items():
                if skill_area not in user_skills['skills']:
                    user_skills['skills'][skill_area] = {
                        'level': 'beginner',
                        'recent_scores': [],
                        'highest_score': 0
                    }
                
                skill_data = user_skills['skills'][skill_area]
                current_score = data['score']
                
                # Update recent scores (keep last 5)
                skill_data['recent_scores'] = (skill_data['recent_scores'] + [current_score])[-5:]
                
                # Update highest score if current is higher
                if current_score > skill_data['highest_score']:
                    skill_data['highest_score'] = current_score
                
                # Calculate average of recent scores
                avg_score = sum(skill_data['recent_scores']) / len(skill_data['recent_scores'])
                
                # Update skill level based on average score
                skill_data['level'] = SkillConfig.determine_skill_level(skill_area, avg_score)
            
            # Save updated skills
            await db.user_skills.update_one(
                {'user_id': user_id},
                {'$set': user_skills},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error updating skill progress: {e}")

    @staticmethod
    async def get_skill_progress(user_id: int) -> Dict[str, Any]:
        """Get user's current skill progress"""
        try:
            user_skills = await db.user_skills.find_one({'user_id': user_id})
            return user_skills['skills'] if user_skills else {}
        except Exception as e:
            logger.error(f"Error getting skill progress: {e}")
            return {}

class LearningPatternAnalyzer:
    """Analyzes learning patterns in user responses"""

    """
    Deprecated: This class is no longer needed as its functionality has been replaced by
    DynamicSkillAnalyzer and SemanticAnalyzer.
    """
    def __init__(self):
        warnings.warn(
            "LearningPatternAnalyzer is deprecated. Use DynamicSkillAnalyzer and SemanticAnalyzer instead.",
            DeprecationWarning,
            stacklevel=2
        )
    
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
        """Analyze response for skill indicators with improved scoring"""
        text = response_text.lower()
        skills = {}
        
        for skill_area, config in SkillConfig.SKILL_PATTERNS.items():
            patterns = config['patterns']
            levels = config['levels']
            
            # Find pattern matches
            matches = [pattern for pattern in patterns if re.search(pattern, text)]
            
            if matches:
                # Calculate base score
                base_score = (len(matches) / len(patterns)) * 100
                
                # Analyze level-specific patterns
                level_scores = {}
                for level, keywords in levels.items():
                    level_matches = [m for m in matches if any(k in m for k in keywords)]
                    level_scores[level] = (len(level_matches) / len(keywords)) * 100
                
                # Calculate weighted score
                weighted_score = (base_score * 0.6 +  # Base patterns
                                sum(level_scores.values()) * 0.4 / len(level_scores))  # Level-specific patterns
                
                skills[skill_area] = {
                    'score': min(100, weighted_score),
                    'indicators': matches,
                    'level_breakdown': level_scores
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


def format_skill_feedback(skills: Dict[str, Any], previous_skills: Dict[str, Any]) -> str:
    """Format skill analysis feedback with progression insights"""
    message = "\n🎯 *Skill Analysis:*\n"
    
    for skill_area, data in skills.items():
        score = data['score']
        prev_data = previous_skills.get(skill_area, {})
        prev_level = prev_data.get('level', 'beginner')
        current_level = SkillConfig.determine_skill_level(skill_area, score)
        
        message += f"\n*{skill_area.replace('_', ' ').title()}*\n"
        message += f"• Score: {score:.1f}/100\n"
        message += f"• Level: {current_level.title()}\n"
        
        # Add progression feedback
        if current_level != prev_level:
            if current_level > prev_level:
                message += "🎉 *Level Up!* Keep up the great work!\n"
        
        # Add skill-specific feedback
        if score >= 80:
            message += "🌟 Excellent mastery of concepts!\n"
        elif score >= 60:
            message += "💪 Good progress! Try incorporating more advanced concepts.\n"
        else:
            message += "📚 Keep practicing! Focus on core concepts first.\n"
    
    return message

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

def analyze_response_quality(response_text: str) -> Dict[str, Any]:
    """Enhanced response quality analysis."""
    try:
        # Basic metrics (keep existing code)
        clean_text = response_text.strip()
        words = clean_text.split()
        sentences = re.split(r'[.!?]+', clean_text)
        
        metrics = {
            'length': len(clean_text),
            'word_count': len(words),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'has_punctuation': bool(re.search(r'[.!?]', clean_text)),
            'includes_details': len(words) > 30
        }

        # Add new dynamic analysis
        skill_analyzer = DynamicSkillAnalyzer()
        trajectory_analyzer = LearningTrajectoryAnalyzer()
        semantic_analyzer = SemanticAnalyzer()

        # Perform analysis
        skill_analysis = skill_analyzer.analyze_response(clean_text)
        semantic_analysis = semantic_analyzer.analyze_response(clean_text)
        
        # Add analyses to metrics
        metrics.update({
            'skill_analysis': skill_analysis,
            'semantic_analysis': semantic_analysis,
            'emerging_interests': trajectory_analyzer.topic_clusters 
        })
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error analyzing response quality: {e}")
        return {
            'length': len(response_text),
            'word_count': len(response_text.split()),
            'error': str(e)
        }


async def format_feedback_message(feedback_list: List[str], quality_metrics: Dict[str, Any], user_id: int) -> str:
    """
    Format feedback into an engaging, well-structured message.
    
    Args:
        feedback_list: List of feedback messages
        quality_metrics: Dictionary containing response quality metrics
        user_id: User's ID for tracking skill progress
        
    Returns:
        Formatted feedback message with emojis and markdown
    """
    try:
        message = "📝 *Response Analysis*\n\n"
        
        # Add quality indicators
        if quality_metrics.get('includes_details'):
            message += "✨ *Detailed Response!* Good level of explanation.\n"
        if quality_metrics.get('has_punctuation'):
            message += "📖 *Well Structured!* Good use of punctuation.\n"
        
        # Add main feedback from lesson
        message += "\n*Feedback:*\n" + "\n".join(feedback_list)

        # Add learning pattern insights
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

        # Add skill progression tracking
        try:
            # Get previous skill progress
            previous_skills = await SkillProgressTracker.get_skill_progress(user_id)
            
            # Update skill progress with new scores
            if 'skills' in quality_metrics:
                await SkillProgressTracker.update_skill_progress(user_id, quality_metrics['skills'])
                
                # Add skill feedback
                skill_feedback = format_skill_feedback(quality_metrics['skills'], previous_skills)
                message += f"\n{skill_feedback}"
        except Exception as skill_error:
            logger.error(f"Error processing skill progress: {skill_error}")
            # Continue without skill feedback rather than failing completely
        
        # Add basic stats
        message += f"\n\n📊 *Response Stats:*\n"
        message += f"• Words: {quality_metrics['word_count']}\n"
        message += f"• Sentences: {quality_metrics['sentence_count']}\n"
        
        return message
        
    except Exception as e:
        logger.error(f"Error formatting feedback message: {e}")
        return "Error generating feedback. Please try again."