"""
Feedback-Aware Enterprise AI Agent - Interactive CLI Demo
Demonstrates closed-loop learning through user feedback
"""
import os
import asyncio
from dotenv import load_dotenv
from feedback_agent import FeedbackAwareAgent

# Load environment variables
load_dotenv()


def print_header():
    """Print welcome header"""
    print("\n" + "="*70)
    print("FEEDBACK-AWARE ENTERPRISE AI AGENT")
    print("Powered by Microsoft Agent Framework + Cosmos DB")
    print("="*70 + "\n")


def print_instructions():
    """Print usage instructions"""
    print("INSTRUCTIONS:")
    print("1. Ask a question (e.g., 'How do I reset my password?')")
    print("2. Read the agent's response")
    print("3. Provide feedback: 'y' (helpful) or 'n' (not helpful)")
    print("4. The agent learns and improves over time")
    print("\nSpecial Commands:")
    print("  'summary'  - View feedback statistics")
    print("  'history'  - View interaction history")
    print("  'quit'     - Exit the demo\n")


async def get_user_feedback() -> bool:
    """Get feedback from user (blocking but async-compatible)"""
    while True:
        feedback_input = input("Was this response helpful? (y/n): ").strip().lower()
        if feedback_input in ['y', 'yes']:
            return True
        elif feedback_input in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'.")


async def display_history(agent: FeedbackAwareAgent):
    """Display recent interaction history"""
    history = agent.feedback_store.get_user_feedback_history(agent.user_id, limit=5)
    
    print("\nRECENT INTERACTION HISTORY")
    print("-" * 60)
    
    if not history:
        print("No interactions yet.")
    else:
        for i, item in enumerate(history, 1):
            feedback_type = "HELPFUL" if item.get("feedback") else "NOT HELPFUL"
            print(f"\n{i}. {feedback_type}")
            print(f"   Q: {item.get('query', 'N/A')[:80]}...")
            print(f"   A: {item.get('response', 'N/A')[:80]}...")
            print(f"   Time: {item.get('timestamp', 'N/A')[:19]}")
    
    print("-" * 60 + "\n")


async def run_demo():
    """Run the interactive CLI demo"""
    
    # Load configuration from environment
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    cosmos_endpoint = os.getenv("COSMOS_DB_ENDPOINT")
    cosmos_key = os.getenv("COSMOS_DB_KEY")
    cosmos_db = os.getenv("COSMOS_DB_NAME")
    cosmos_container = os.getenv("COSMOS_DB_CONTAINER")
    
    # Validate environment
    if not all([endpoint, api_key, deployment, cosmos_endpoint, cosmos_key]):
        print("Error: Missing required environment variables!")
        print("Required: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT")
        print("          COSMOS_DB_ENDPOINT, COSMOS_DB_KEY")
        return
    
    # Initialize agent
    print("Initializing Feedback-Aware Agent...")
    try:
        agent = FeedbackAwareAgent(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            cosmos_endpoint=cosmos_endpoint,
            cosmos_key=cosmos_key,
            db_name=cosmos_db,
            container_name=cosmos_container,
            user_id="demo_user"
        )
        
        await agent.initialize_thread()
        print("Agent ready.\n")
    except Exception as e:
        print(f"Error initializing agent: {e}")
        return
    
    # Print headers and instructions
    print_header()
    print_instructions()
    
    # Main conversation loop
    interaction_count = 0
    
    try:
        while True:
            # Get user input
            print("-" * 70)
            user_input = input("You: ").strip()
            
            if not user_input:
                print("Please enter a question or command.")
                continue
            
            # Handle special commands
            if user_input.lower() == "quit":
                print("\nThank you for using the Feedback-Aware Agent!")
                break
            
            if user_input.lower() == "summary":
                agent.display_feedback_summary()
                continue
            
            if user_input.lower() == "history":
                await display_history(agent)
                continue
            
            # Get response from agent
            try:
                response = await agent.query(user_input)
                interaction_count += 1
                
                print(f"\nAgent: {response}\n")
                
                # Get feedback
                is_helpful = await get_user_feedback()
                
                # Store feedback
                await agent.store_feedback(user_input, response, is_helpful)
                
                # Show learning message
                if is_helpful:
                    print("Agent learning from positive feedback...")
                else:
                    print("Agent will improve based on your feedback...")
                
                print()
                
            except Exception as e:
                print(f"Error processing query: {e}")
                continue
    
    except KeyboardInterrupt:
        print("\nDemo interrupted.")
    
    finally:
        # Cleanup
        agent.close()
        print("Resources cleaned up.")
        print(f"Total interactions: {interaction_count}")
        agent.display_feedback_summary()


def main():
    """Entry point for the demo"""
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
