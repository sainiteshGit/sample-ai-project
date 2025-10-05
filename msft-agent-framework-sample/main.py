import os
import asyncio
from agent_framework.azure import AzureOpenAIResponsesClient

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, that's ok

async def main():
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is required") 
    if not deployment:
        raise ValueError("AZURE_OPENAI_DEPLOYMENT environment variable is required")

    print("🔵 DEMO: 'SERVICE' Chat History Storage")
    print("📋 NOTE: Actually using IN-MEMORY storage with process-shared threads")
    print("=" * 70)

    # Azure OpenAI Responses agent - Currently using IN-MEMORY storage
    # (True service storage would require additional configuration)
    service_agent = AzureOpenAIResponsesClient(
        endpoint=endpoint, 
        api_key=api_key, 
        deployment_name=deployment
    ).create_agent(
        name="ServiceAgent",
        instructions="You are a helpful assistant.",
    )

    # Create a thread (stored in-memory within this process)
    # NOTE: Despite the name 'service_thread', this is actually in-memory storage
    service_thread = service_agent.get_new_thread()
    
    print(f"📋 Thread initialized: {service_thread.is_initialized}")
    print(f"📋 Service thread ID: {service_thread.service_thread_id}")
    
    # Start conversation
    print("User: Hi! I'm Alice and I work in marketing.")
    response1 = await service_agent.run("Hi! I'm Alice and I work in marketing.", thread=service_thread)
    print(f"Agent: {response1}\n")
    
    # Continue conversation - history managed by service
    print("User: What's my name and job?")
    response2 = await service_agent.run("What's my name and job?", thread=service_thread)
    print(f"Agent: {response2}\n")
    
    # Check thread state after conversation
    serialized_data = await service_thread.serialize()
    has_local_messages = 'messages' in str(serialized_data)
    has_service_id = serialized_data.get('service_thread_id') is not None
    
    print(f"📋 ACTUAL STORAGE ANALYSIS:")
    print(f"   - Thread has local messages: {has_local_messages}")
    print(f"   - Thread has service ID: {has_service_id}")
    print(f"   - Storage type: {'SERVICE' if has_service_id and not has_local_messages else 'IN-MEMORY'}")
    print("✅ This works because thread is shared within the process!")
    print("💡 NOTE: For true Azure service storage, additional config would be needed")
    
    print("\n🟢 DEMO: CUSTOM Chat History Storage")
    print("📋 NOTE: This shows true custom storage with manual history management")
    print("=" * 70)

    # REAL custom chat history storage implementation
    class CustomChatHistory:
        def __init__(self):
            self.messages = []
        
        def add_message(self, role: str, content: str):
            self.messages.append({"role": role, "content": content})
        
        def get_full_conversation(self):
            conversation = ""
            for msg in self.messages:
                conversation += f"{msg['role']}: {msg['content']}\n"
            return conversation

    # Create custom history manager
    custom_history = CustomChatHistory()
    
    # Create a STATELESS agent for custom history (no thread management)
    stateless_agent = AzureOpenAIResponsesClient(
        endpoint=endpoint, 
        api_key=api_key, 
        deployment_name=deployment
    ).create_agent(
        name="StatelessAgent",
        instructions="You are a helpful assistant. Respond based on the conversation history provided.",
    )
    
    # REAL conversation with custom storage + LLM calls
    print("User: Hi! I'm Bob and I'm a software engineer.")
    custom_history.add_message("user", "Hi! I'm Bob and I'm a software engineer.")
    
    # Call LLM with just the current message (no service history)
    response1 = await stateless_agent.run("Hi! I'm Bob and I'm a software engineer.")
    custom_history.add_message("assistant", response1)
    print(f"Agent: {response1}\n")
    
    # Continue conversation - now we need to send FULL history to get context
    print("User: What do I do for work?")
    custom_history.add_message("user", "What do I do for work?")
    
    # 🔥 KEY DIFFERENCE: We must manually send FULL conversation history
    print("📝 Sending FULL conversation history to LLM (manual management):")
    full_context = custom_history.get_full_conversation()
    print(full_context)
    print("⚠️  In contrast, the 'service' demo above automatically manages context")
    
    # Call LLM with FULL conversation context
    response2 = await stateless_agent.run(f"Based on this conversation history:\n{full_context}\nPlease respond to the latest message.")
    custom_history.add_message("assistant", response2)
    print(f"Agent: {response2}")
    
    print("✅ This works because WE manage the history and send it to the LLM!")
    
    print("\n🎯 SUMMARY OF DIFFERENCES:")
    print("=" * 50)
    print("🔵 'Service' Demo (Thread-based):")
    print("   - Uses AgentThread for automatic context management")
    print("   - Storage: In-memory within process (not true Azure service)")
    print("   - Thread shared between agent instances in same process")
    print("   - No manual history management needed")
    print("\n🟢 Custom Demo (Manual):")
    print("   - Manual conversation history tracking")
    print("   - YOU control what context gets sent")
    print("   - More work but complete control over storage")
    print("   - Can store in any database/system you choose")

if __name__ == "__main__":
    asyncio.run(main())
