"""
Feedback-Aware Enterprise AI Agent
Uses Microsoft Agent Framework with feedback-driven learning
"""
import os
import asyncio
from typing import Optional, Dict, Any
from agent_framework.azure import AzureOpenAIChatClient
from feedback_store import FeedbackStore


class FeedbackAwareAgent:
    """
    An AI agent that learns from user feedback without retraining the LLM.
    Uses Microsoft Agent Framework for orchestration and Cosmos DB for feedback storage.
    """
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        cosmos_endpoint: str,
        cosmos_key: str,
        db_name: str,
        container_name: str,
        user_id: str = "default_user"
    ):
        """Initialize the feedback-aware agent"""
        self.user_id = user_id
        
        # Initialize Azure OpenAI client
        self.openai_client = AzureOpenAIChatClient(
            endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment
        )
        
        # Create agent with feedback-aware instructions
        self.agent = self.openai_client.create_agent(
            name="FeedbackAwareAgent",
            instructions=self._get_system_instructions()
        )
        
        # Initialize feedback store
        self.feedback_store = FeedbackStore(
            endpoint=cosmos_endpoint,
            key=cosmos_key,
            database_name=db_name,
            container_name=container_name
        )
        
        # Thread for conversation history
        self.thread = None
    
    def _get_system_instructions(self) -> str:
        """Get system instructions with feedback context"""
        base_instructions = """You are a helpful enterprise AI assistant that learns from user feedback.
        
Your goals:
1. Provide clear, accurate, and helpful responses
2. Learn from user feedback to improve future responses
3. Maintain consistency with organizational standards
4. Adapt your tone and terminology based on user preferences

Guidelines:
- Be concise and direct
- Use organizational terminology when appropriate
- Acknowledge feedback and improve accordingly
- Maintain a professional yet friendly tone"""
        
        return base_instructions
    
    def _build_feedback_context(self) -> str:
        """Build context from feedback history to augment prompts"""
        feedback_summary = self.feedback_store.get_feedback_summary(self.user_id)
        helpful_examples = self.feedback_store.get_helpful_feedback(self.user_id, limit=3)
        
        context_parts = []
        
        # Add feedback statistics
        if feedback_summary["total_interactions"] > 0:
            context_parts.append(
                f"\n[FEEDBACK LEARNING]\n"
                f"Based on {feedback_summary['total_interactions']} past interactions:\n"
                f"- User found {feedback_summary['helpful_count']} responses helpful\n"
                f"- User found {feedback_summary['not_helpful_count']} responses unhelpful\n"
                f"- Success rate: {feedback_summary['helpful_ratio']:.1%}\n"
                f"\nAdjust your response style based on what worked before."
            )
        
        # Add recent helpful responses as examples
        if helpful_examples:
            context_parts.append(
                "\n[EXAMPLES OF HELPFUL RESPONSES]"
            )
            for ex in helpful_examples:
                context_parts.append(
                    f"\nQ: {ex['query']}\n"
                    f"A: {ex['response']}"
                )
        
        return "".join(context_parts) if context_parts else ""
    
    async def initialize_thread(self):
        """Initialize conversation thread"""
        if self.thread is None:
            self.thread = self.agent.get_new_thread()
    
    async def query(self, user_input: str) -> str:
        """
        Process a user query and generate response with feedback awareness
        """
        if self.thread is None:
            await self.initialize_thread()
        
        # Build feedback context
        feedback_context = self._build_feedback_context()
        
        # Augment the query with feedback context if available
        augmented_input = user_input
        if feedback_context:
            augmented_input = f"{user_input}\n\n[FEEDBACK CONTEXT:{feedback_context}]"
        
        # Get response from agent
        response = await self.agent.run(augmented_input, thread=self.thread)
        
        # Convert response to string if it's an object
        response_text = str(response) if response else ""
        
        return response_text
    
    async def store_feedback(self, query: str, response: str, is_helpful: bool):
        """Store user feedback in Cosmos DB"""
        feedback_id = self.feedback_store.store_feedback(
            user_id=self.user_id,
            query=query,
            response=response,
            feedback=is_helpful,
            context={
                "feedback_session": True,
                "improvement_needed": not is_helpful
            }
        )
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get current feedback statistics"""
        return self.feedback_store.get_feedback_summary(self.user_id)
    
    def display_feedback_summary(self):
        """Display feedback summary in CLI"""
        summary = self.get_feedback_summary()
        
        print(f"\nFEEDBACK SUMMARY FOR {self.user_id.upper()}")
        print("-" * 50)
        
        if summary["total_interactions"] == 0:
            print("No feedback collected yet.")
        else:
            print(f"Total Interactions: {summary['total_interactions']}")
            print(f"Helpful: {summary['helpful_count']} ({summary['helpful_count'] / summary['total_interactions'] * 100:.1f}%)")
            print(f"Needs Improvement: {summary['not_helpful_count']}")
            print(f"Helpful Ratio: {summary['helpful_ratio']:.1%}")
        
        print("-" * 50 + "\n")
    
    def close(self):
        """Clean up resources"""
        if self.feedback_store:
            self.feedback_store.close()
