from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging
from services.database import db

logger = logging.getLogger(__name__)

class LearningInsightsManager:
    """
    Manages storage and retrieval of deep learning insights for each user.
    Integrates with existing MongoDB structure.
    """

    @staticmethod
    async def store_learning_insights(user_id: int, insights: Dict[str, Any]) -> bool:
        """
        Store comprehensive learning insights for a user.
        """
        try:
            timestamp = datetime.now(timezone.utc)
            
            insight_doc = {
                "timestamp": timestamp,
                "emerging_interests": insights.get("emerging_interests", []),
                "unplanned_skills": insights.get("unplanned_skills", []),
                "support_areas": insights.get("support_areas", []),
                "learning_trajectory": insights.get("learning_trajectory", {}),
                "suggested_paths": insights.get("suggested_paths", [])
            }
            
            result = await db.learning_insights.update_one(
                {"user_id": user_id},
                {
                    "$push": {
                        "insights": {
                            "$each": [insight_doc],
                            "$sort": {"timestamp": -1},
                            "$slice": 50  # Keep last 50 insights
                        }
                    },
                    "$setOnInsert": {
                        "user_id": user_id,
                        "created_at": timestamp
                    }
                },
                upsert=True
            )
            
            if result.acknowledged:
                logger.info(f"Stored learning insights for user {user_id}")
                return True
            
            logger.error(f"Failed to store insights for user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error storing learning insights: {e}")
            return False

    @staticmethod
    async def get_user_insights(user_id: int, limit: int = 10) -> Optional[Dict[str, Any]]:
        """
        Get learning insights for a specific user.
        """
        try:
            insights = await db.learning_insights.find_one(
                {"user_id": user_id},
                {"insights": {"$slice": -limit}}  # Get most recent insights
            )
            
            if insights:
                insights.pop('_id', None)
                return insights
                
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving learning insights: {e}")
            return None

    @staticmethod
    async def get_support_recommendations(user_id: int) -> List[Dict[str, Any]]:
        """Get actionable support recommendations for a user."""
        try:
            insights = await db.learning_insights.find_one({"user_id": user_id})
            
            if not insights or not insights.get('insights'):
                return []
            
            latest_insight = insights['insights'][-1]
            
            recommendations = []

            for area in latest_insight.get('support_areas', []):
                recommendations.append({
                    "type": "support_needed",
                    "area": area,
                    "priority": "high" if area in latest_insight.get('recurring_gaps', []) else "medium"
                })

            for interest in latest_insight.get('emerging_interests', []):
                recommendations.append({
                    "type": "emerging_interest",
                    "area": interest,
                    "priority": "medium"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting support recommendations: {e}")
            return []

    @staticmethod
    async def get_learning_trajectory(user_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed learning trajectory analysis for a user."""
        try:
            insights = await db.learning_insights.find_one({"user_id": user_id})
            
            if not insights or not insights.get('insights'):
                return None
            
            trajectories = [
                insight['learning_trajectory'] 
                for insight in insights['insights']
                if 'learning_trajectory' in insight
            ]
            
            if not trajectories:
                return None
            
            latest = trajectories[-1]
            historical = trajectories[:-1] if len(trajectories) > 1 else []
            
            return {
                "current_trajectory": latest,
                "historical_progression": historical,
                "velocity": latest.get('velocity'),
                "suggested_paths": latest.get('suggested_paths', []),
                "timestamp": datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error(f"Error getting learning trajectory: {e}")
            return None

    @staticmethod
    async def get_unplanned_skills_report() -> List[Dict[str, Any]]:
        """Generate report of commonly occurring unplanned skills across users."""
        try:
            pipeline = [
                {"$unwind": "$insights"},
                {"$unwind": "$insights.unplanned_skills"},
                {
                    "$group": {
                        "_id": "$insights.unplanned_skills",
                        "count": {"$sum": 1},
                        "users": {"$addToSet": "$user_id"}
                    }
                },
                {"$sort": {"count": -1}}
            ]
            
            results = await db.learning_insights.aggregate(pipeline).to_list(None)

            skills_report = [
                {
                    "skill": result["_id"],
                    "occurrence_count": result["count"],
                    "unique_users": len(result["users"]),
                    "potential_gap": result["count"] > 5
                }
                for result in results
            ]
            
            return skills_report
            
        except Exception as e:
            logger.error(f"Error generating unplanned skills report: {e}")
            return []

    @staticmethod
    async def get_admin_dashboard_data() -> Dict[str, Any]:
        """Get aggregated insights for admin dashboard."""
        try:
            dashboard_data = {
                "total_users_analyzed": await db.learning_insights.count_documents({}),
                "common_support_areas": [],
                "emerging_trends": [],
                "skill_gaps": [],
                "learning_paths": [],
                "timestamp": datetime.now(timezone.utc)
            }
            
            support_areas_pipeline = [
                {"$unwind": "$insights"},
                {"$unwind": "$insights.support_areas"},
                {
                    "$group": {
                        "_id": "$insights.support_areas",
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]

            support_areas = await db.learning_insights.aggregate(support_areas_pipeline).to_list(None)
            dashboard_data["common_support_areas"] = [
                {"area": area["_id"], "count": area["count"]}
                for area in support_areas
            ]
            
            trends_pipeline = [
                {"$unwind": "$insights"},
                {"$unwind": "$insights.emerging_interests"},
                {
                    "$group": {
                        "_id": "$insights.emerging_interests",
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]

            trends = await db.learning_insights.aggregate(trends_pipeline).to_list(None)
            dashboard_data["emerging_trends"] = [
                {"trend": trend["_id"], "count": trend["count"]}
                for trend in trends
            ]
            
            skill_gaps = await LearningInsightsManager.get_unplanned_skills_report()
            dashboard_data["skill_gaps"] = [gap for gap in skill_gaps if gap["potential_gap"]]
            
            paths_pipeline = [
                {"$unwind": "$insights"},
                {"$unwind": "$insights.suggested_paths"},
                {
                    "$group": {
                        "_id": "$insights.suggested_paths",
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]

            paths = await db.learning_insights.aggregate(paths_pipeline).to_list(None)
            dashboard_data["learning_paths"] = [
                {"path": path["_id"], "frequency": path["count"]}
                for path in paths
            ]
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error generating admin dashboard data: {e}")
            return {}
