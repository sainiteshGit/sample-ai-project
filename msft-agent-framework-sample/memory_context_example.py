"""
Memory and Context Example: Personalized Assistant
Demonstrates how to add memory to an agent using ContextProvider in Microsoft Agent Framework
"""

import asyncio
import os
from pydantic import BaseModel
from typing import Any, Sequence
from dotenv import load_dotenv

from agent_framework import ContextProvider, Context
from agent_framework import ChatMessage, ChatOptions
from agent_framework.azure import AzureOpenAIChatClient

# Load environment variables
load_dotenv()


# ============================================================================
# STEP 1: Define Your Memory Model
# ============================================================================

class UserInfo(BaseModel):
    """User information to remember across interactions."""
    name: str | None = None
    age: int | None = None


# ============================================================================
# STEP 2: Create the ContextProvider
# ============================================================================

class UserInfoMemory(ContextProvider):
    """Remembers user name and age, enforces collection before answering."""
    
    def __init__(
        self, 
        chat_client, 
        user_info: UserInfo | None = None, 
        **kwargs: Any
    ):
        """
        Initialize memory.
        
        Args:
            chat_client: Client for extracting structured data
            user_info: Existing user info (for thread restoration)
            **kwargs: Used to restore from serialized state
        """
        self._chat_client = chat_client
        
        if user_info:
            self.user_info = user_info
        elif kwargs:
            self.user_info = UserInfo.model_validate(kwargs)
        else:
            self.user_info = UserInfo()  # Empty memory
    
    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Extract user information from messages after each agent call.
        
        This runs AFTER the LLM responds, allowing us to update memory.
        """
        # Filter for user messages only
        if isinstance(request_messages, ChatMessage):
            request_messages = [request_messages]
            
        user_messages = [
            msg for msg in request_messages 
            if hasattr(msg, "role") and msg.role.value == "user"
        ]

        # If we're missing info and have user messages, try to extract
        if (self.user_info.name is None or self.user_info.age is None) and user_messages:
            try:
                # Use structured output to extract user info
                result = await self._chat_client.get_response(
                    messages=request_messages,
                    chat_options=ChatOptions(
                        instructions="Extract the user's name and age from the message if present. If not present return nulls.",
                        response_format=UserInfo,
                    ),
                )

                # Update only missing fields
                if result.value:
                    if self.user_info.name is None and result.value.name:
                        self.user_info.name = result.value.name
                    if self.user_info.age is None and result.value.age:
                        self.user_info.age = result.value.age

            except Exception as e:
                pass  # Extraction failed, continue without updating
    
    async def invoking(
        self, 
        messages: ChatMessage | Sequence[ChatMessage], 
        **kwargs: Any
    ) -> Context:
        """
        Provide user information context before each agent call.
        
        This runs BEFORE the LLM is invoked, allowing us to inject instructions.
        """
        instructions: list[str] = []

        # If name is missing, instruct agent to ask for it
        if self.user_info.name is None:
            instructions.append(
                "Ask the user for their name and politely decline to answer "
                "any questions until they provide it."
            )
        else:
            instructions.append(f"The user's name is {self.user_info.name}.")

        # If age is missing, instruct agent to ask for it
        if self.user_info.age is None:
            instructions.append(
                "Ask the user for their age and politely decline to answer "
                "any questions until they provide it."
            )
        else:
            instructions.append(f"The user's age is {self.user_info.age}.")
        
        # Return context with dynamic instructions
        return Context(instructions=" ".join(instructions))
    
    def serialize(self) -> str:
        """Serialize user info for thread persistence."""
        return self.user_info.model_dump_json()


# ============================================================================
# STEP 3: Create Agent with Memory
# ============================================================================

async def create_agent_with_memory():
    """Create an agent with memory provider attached."""
    
    # Get Azure OpenAI configuration
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        raise ValueError(
            "Missing Azure OpenAI configuration. Please set:\n"
            "  - AZURE_OPENAI_ENDPOINT\n"
            "  - AZURE_OPENAI_API_KEY\n"
            "  - AZURE_OPENAI_DEPLOYMENT"
        )
    
    # Create Azure OpenAI client
    chat_client = AzureOpenAIChatClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    )

    # Create memory provider
    memory_provider = UserInfoMemory(chat_client)

    # Create agent with memory
    agent = chat_client.create_agent(
        name="PersonalAssistant",
        instructions="You are a friendly assistant. Always address the user by their name when you know it.",
        context_providers=memory_provider  # ← Attach memory
    )
    
    return agent, memory_provider


# ============================================================================
# EXAMPLE: Conversation with Memory
# ============================================================================

async def demo_memory_conversation():
    """Demonstrate agent remembering user information across interactions."""
    
    print("\nAgent with Memory - Conversation Demo")
    print("=" * 70)
    
    # Create agent with memory
    agent, memory_provider = await create_agent_with_memory()
    
    # Create a new thread for the conversation
    thread = agent.get_new_thread()
    
    # Turn 1: User asks a question without providing info
    print("\nUser: Hello, what is the square root of 9?")
    response1 = await agent.run("Hello, what is the square root of 9?", thread=thread)
    print(f"Agent: {response1.text}")
    
    # Turn 2: User provides name
    print("\nUser: My name is Sarah")
    response2 = await agent.run("My name is Sarah", thread=thread)
    print(f"Agent: {response2.text}")
    
    # Turn 3: User provides age
    print("\nUser: I am 28 years old")
    response3 = await agent.run("I am 28 years old", thread=thread)
    print(f"Agent: {response3.text}")
    
    # Turn 4: User asks the original question again
    print("\nUser: So, what is the square root of 9?")
    response4 = await agent.run("So, what is the square root of 9?", thread=thread)
    print(f"Agent: {response4.text}")
    
    # Turn 5: Test memory recall
    print("\nUser: What's my name and age?")
    response5 = await agent.run("What's my name and age?", thread=thread)
    print(f"Agent: {response5.text}")
    
    # Access memory directly
    print("\n" + "=" * 70)
    user_memory = thread.context_provider.providers[0]
    print(f"Memory State: {user_memory.serialize()}")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Run memory and context demonstration."""
    
    print("\nMemory and Context with Microsoft Agent Framework")
    print("=" * 70)
    
    await demo_memory_conversation()


if __name__ == "__main__":
    asyncio.run(main())
