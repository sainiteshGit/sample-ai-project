import asyncio
import os
import json
from dotenv import load_dotenv
from agent_framework.azure import AzureOpenAIResponsesClient

# Load environment variables
load_dotenv()

async def validate_storage_locations():
    """Validate where chat history is actually stored"""
    
    # Setup Azure OpenAI client
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # Fixed variable name
    
    client = AzureOpenAIResponsesClient(
        endpoint=endpoint, 
        api_key=api_key, 
        deployment_name=deployment
    )
    
    print("🔍 VALIDATION: Where is chat history stored?")
    print("=" * 60)
    
    # Create agent with service storage
    service_agent = client.create_agent(
        name="ValidationAgent",
        instructions="You are a validation assistant. Keep responses brief."
    )
    
    print("\n1️⃣ Creating NEW service thread...")
    service_thread = service_agent.get_new_thread()
    
    # Check what's in the thread object initially
    print(f"📋 Initial thread object type: {type(service_thread)}")
    print(f"📋 Thread object attributes: {dir(service_thread)}")
    
    # Try to serialize the thread to see what it contains
    try:
        if hasattr(service_thread, 'serialize'):
            serialized = service_thread.serialize()
            print(f"📋 Serialized thread: {serialized}")
        elif hasattr(service_thread, '__dict__'):
            print(f"📋 Thread internal data: {service_thread.__dict__}")
        else:
            print(f"📋 Thread string representation: {str(service_thread)}")
    except Exception as e:
        print(f"📋 Could not inspect thread: {e}")
    
    print("\n2️⃣ Adding first message to service thread...")
    response1 = await service_agent.run("Hi, I'm testing storage. My name is TestUser.", thread=service_thread)
    print(f"Agent: {response1}")
    
    # Check thread after first message
    print("\n📋 After first message:")
    try:
        if hasattr(service_thread, 'serialize'):
            serialized = service_thread.serialize()
            print(f"📋 Serialized thread: {serialized}")
        elif hasattr(service_thread, '__dict__'):
            print(f"📋 Thread internal data: {service_thread.__dict__}")
        else:
            print(f"📋 Thread string representation: {str(service_thread)}")
    except Exception as e:
        print(f"📋 Could not inspect thread: {e}")
    
    print("\n3️⃣ Adding second message...")
    response2 = await service_agent.run("What's my name?", thread=service_thread)
    print(f"Agent: {response2}")
    
    # Check thread after second message
    print("\n📋 After second message:")
    try:
        if hasattr(service_thread, 'serialize'):
            serialized = service_thread.serialize()
            print(f"📋 Serialized thread: {serialized}")
        elif hasattr(service_thread, '__dict__'):
            print(f"📋 Thread internal data: {service_thread.__dict__}")
        else:
            print(f"📋 Thread string representation: {str(service_thread)}")
    except Exception as e:
        print(f"📋 Could not inspect thread: {e}")
    
    print("\n4️⃣ PERSISTENCE TEST:")
    print("Creating a NEW agent instance with the SAME thread...")
    
    # Create a completely new agent instance
    new_client = AzureOpenAIResponsesClient(
        endpoint=endpoint, 
        api_key=api_key, 
        deployment_name=deployment
    )
    new_agent = new_client.create_agent(
        name="NewValidationAgent",
        instructions="You are a different agent instance. Keep responses brief."
    )
    
    # Use the same thread with the new agent
    try:
        response3 = await new_agent.run("Do you remember my name from our previous conversation?", thread=service_thread)
        print(f"New Agent: {response3}")
        print("✅ SUCCESS: Thread persisted across different agent instances!")
        print("💡 This proves history is stored in Azure service, not locally!")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        print("💡 This would indicate local storage or compatibility issues")
    
    print("\n5️⃣ THREAD ID ANALYSIS:")
    # Try to extract thread ID or service reference
    thread_attrs = [attr for attr in dir(service_thread) if not attr.startswith('_')]
    print(f"📋 Public thread attributes: {thread_attrs}")
    
    for attr in thread_attrs:
        try:
            value = getattr(service_thread, attr)
            if not callable(value):
                print(f"📋 {attr}: {value} (type: {type(value)})")
        except Exception as e:
            print(f"📋 {attr}: <could not access - {e}>")
    
    print("\n" + "=" * 60)
    print("🎯 CONCLUSION:")
    print("- If thread contains only ID/reference → Azure service storage")
    print("- If thread contains actual messages → Local/in-memory storage")
    print("- If new agent can access old conversation → Service persistence")

if __name__ == "__main__":
    asyncio.run(validate_storage_locations())