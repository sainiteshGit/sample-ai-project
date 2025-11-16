"""
Multi-Turn Conversation Demo - Building Context Across Dialogues
"""

import os
import asyncio

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent_framework.azure import AzureOpenAIChatClient


async def demo1_shopping_assistant():
    """Demo 1: Shopping Assistant - Context Preservation"""
    print("\n" + "="*70)
    print("DEMO 1: Shopping Assistant with Multi-Turn Memory")
    print("="*70)
    
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    client = AzureOpenAIChatClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    )
    
    agent = client.create_agent(
        name="ShoppingAssistant",
        instructions="You are a helpful shopping assistant. Keep responses concise."
    )
    
    thread = agent.get_new_thread()
    
    print("\nUser: Show me laptops under $1000")
    response1 = await agent.run("Show me laptops under $1000", thread=thread)
    print(f"🤖 Agent: {response1}\n")
    
    print("User: What about the second one?")
    response2 = await agent.run("What about the second one?", thread=thread)
    print(f"Agent: {response2}\n")
    
    print("Agent remembered the laptop list!")


async def main():
    print("\nMULTI-TURN CONVERSATION DEMO")
    print("="*70)
    
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        raise ValueError("Azure OpenAI environment variables required")
    
    print(f"Using deployment: {deployment}")
    
    await demo1_shopping_assistant()
    
    print("\n DEMO COMPLETE\n")


if __name__ == "__main__":
    asyncio.run(main())
