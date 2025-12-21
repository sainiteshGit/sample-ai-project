"""
Demo: Show how feedback influences agent responses
This demonstrates the closed-loop learning mechanism
"""
import os
import asyncio
from dotenv import load_dotenv
from feedback_agent import FeedbackAwareAgent

load_dotenv()


async def demo_feedback_influence():
    """Demonstrate how feedback influences future responses"""
    
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    cosmos_endpoint = os.getenv("COSMOS_DB_ENDPOINT")
    cosmos_key = os.getenv("COSMOS_DB_KEY")
    
    if not all([endpoint, api_key, deployment, cosmos_endpoint, cosmos_key]):
        print("Error: Missing environment variables")
        return
    
    print("="*70)
    print("FEEDBACK-AWARE AGENT: LEARNING DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how feedback shapes agent behavior\n")
    
    agent = FeedbackAwareAgent(
        endpoint=endpoint,
        api_key=api_key,
        deployment=deployment,
        cosmos_endpoint=cosmos_endpoint,
        cosmos_key=cosmos_key,
        db_name="feedback-agent-db",
        container_name="feedback",
        user_id="learning_demo"
    )
    
    await agent.initialize_thread()
    
    # Interaction 1
    print("INTERACTION 1")
    print("-"*70)
    query1 = "Explain AI in simple terms"
    print(f"User: {query1}\n")
    
    response1 = await agent.query(query1)
    print(f"Agent Response:\n{response1}\n")
    
    print("User: This is too technical. Please simplify.")
    feedback_1 = False  # Not helpful
    await agent.store_feedback(query1, response1, feedback_1)
    print("Feedback stored: NOT HELPFUL (too technical)\n")
    
    # Interaction 2 - Agent should now consider feedback
    print("\n" + "="*70)
    print("INTERACTION 2 (Agent considers feedback from Interaction 1)")
    print("-"*70)
    query2 = "What is machine learning?"
    print(f"User: {query2}\n")
    
    # Show the feedback context that will be added to the prompt
    feedback_context = agent._build_feedback_context()
    print("FEEDBACK CONTEXT ADDED TO PROMPT:")
    print("-"*70)
    print(feedback_context)
    print("-"*70 + "\n")
    
    response2 = await agent.query(query2)
    print(f"Agent Response (should be SIMPLER based on feedback):\n{response2}\n")
    
    print("User: Much better! Simple and clear.")
    feedback_2 = True  # Helpful
    await agent.store_feedback(query2, response2, feedback_2)
    print("Feedback stored: HELPFUL (simple explanation)\n")
    
    # Show learning progress
    print("\n" + "="*70)
    print("FEEDBACK LEARNING PROGRESS")
    print("-"*70)
    agent.display_feedback_summary()
    
    agent.close()
    print("Demo complete: Agent learned from feedback!\n")


if __name__ == "__main__":
    asyncio.run(demo_feedback_influence())
