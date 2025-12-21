"""
Cosmos DB Feedback Store Module
Manages storage and retrieval of user feedback for the feedback-aware agent
"""
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from azure.cosmos import CosmosClient, PartitionKey


class FeedbackStore:
    """Manages feedback storage and retrieval from Cosmos DB"""
    
    def __init__(self, endpoint: str, key: str, database_name: str, container_name: str):
        """Initialize Cosmos DB connection"""
        self.client = CosmosClient(endpoint, credential=key)
        self.database = self.client.create_database_if_not_exists(id=database_name)
        
        # Create container with partition key
        self.container = self.database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/user_id")
        )
    
    def store_feedback(
        self,
        user_id: str,
        query: str,
        response: str,
        feedback: bool,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store feedback in Cosmos DB"""
        feedback_item = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "query": query,
            "response": response,
            "feedback": feedback,  # True = helpful, False = not helpful
            "feedback_type": "helpful" if feedback else "not_helpful",
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }
        
        result = self.container.create_item(body=feedback_item)
        return feedback_item["id"]
    
    def get_user_feedback_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Retrieve user's recent feedback history"""
        query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit"
        
        items = list(self.container.query_items(
            query=query,
            parameters=[
                {"name": "@user_id", "value": user_id},
                {"name": "@limit", "value": limit}
            ]
        ))
        
        return items
    
    def get_helpful_feedback(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get user's helpful feedback for reference"""
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.feedback = true ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit"
        
        items = list(self.container.query_items(
            query=query,
            parameters=[
                {"name": "@user_id", "value": user_id},
                {"name": "@limit", "value": limit}
            ]
        ))
        
        return items
    
    def get_feedback_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary statistics of user feedback"""
        history = self.get_user_feedback_history(user_id, limit=100)
        
        if not history:
            return {
                "total_interactions": 0,
                "helpful_count": 0,
                "not_helpful_count": 0,
                "helpful_ratio": 0.0
            }
        
        helpful_count = sum(1 for item in history if item.get("feedback", False))
        not_helpful_count = len(history) - helpful_count
        
        return {
            "total_interactions": len(history),
            "helpful_count": helpful_count,
            "not_helpful_count": not_helpful_count,
            "helpful_ratio": helpful_count / len(history) if history else 0.0
        }
    
    def close(self):
        """Close database connection"""
        if self.client:
            try:
                self.client.close()
            except AttributeError:
                pass  # CosmosClient may not have close method
