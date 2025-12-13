"""
Reinforcement Learning Example: User Preference Learning Agent
Demonstrates how RL feedback loops drive agent adaptation using Microsoft Agent Framework
"""

import asyncio
import os
from pydantic import BaseModel, Field
from typing import Any, Sequence
from dotenv import load_dotenv

from agent_framework import ContextProvider, Context
from agent_framework import ChatMessage, ChatOptions
from agent_framework.azure import AzureOpenAIChatClient

load_dotenv()


# ============================================================================
# STEP 1: Define RL Models
# ============================================================================

class UserPreferences(BaseModel):
    """Learned policy: what we know about user preferences."""
    technical_depth: str = "medium"  # "basic", "medium", "advanced"
    prefer_examples: bool = True
    response_length: str = "balanced"  # "concise", "balanced", "detailed"
    feedback_count: int = 0
    positive_feedback: int = 0


class UserFeedback(BaseModel):
    """Reward signal: user's evaluation of the agent's response."""
    rating: int = Field(..., ge=1, le=5, description="1-5 rating of response quality")
    suggestion: str | None = Field(None, description="How to improve the response")


# ============================================================================
# STEP 2: RL Context Provider (Learning from Feedback)
# ============================================================================

class PreferenceLearningProvider(ContextProvider):
    """
    Implements RL feedback loop: learns user preferences through feedback.
    
    Policy Update Formula:
    - Track positive/negative feedback
    - Adjust technical depth based on reactions
    - Refine response style based on suggestions
    """
    
    def __init__(
        self,
        chat_client,
        preferences: UserPreferences | None = None,
        **kwargs: Any
    ):
        self._chat_client = chat_client
        
        if preferences:
            self.preferences = preferences
        elif kwargs:
            self.preferences = UserPreferences.model_validate(kwargs)
        else:
            self.preferences = UserPreferences()
    
    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Extract feedback after each agent call.
        This is the reward signal that drives RL updates.
        """
        if isinstance(request_messages, ChatMessage):
            request_messages = [request_messages]
        
        user_messages = [
            msg for msg in request_messages
            if hasattr(msg, "role") and msg.role.value == "user"
        ]

        if user_messages:
            try:
                # Extract feedback using structured output
                result = await self._chat_client.get_response(
                    messages=request_messages,
                    chat_options=ChatOptions(
                        instructions="Extract feedback rating (1-5) about the previous response. If user gives thumbs up/positive feedback, rate 5. If negative, rate 1. If mixed, rate 3. If no clear feedback, return null.",
                        response_format=UserFeedback,
                    ),
                )

                if result.value and result.value.rating:
                    # RL Update: Adjust policy based on reward
                    self._update_policy(result.value)

            except Exception:
                pass
    
    def _update_policy(self, feedback: UserFeedback):
        """Update learned preferences based on feedback (reward signal)."""
        self.preferences.feedback_count += 1
        
        if feedback.rating >= 4:
            self.preferences.positive_feedback += 1
        
        # Learn from feedback patterns
        if feedback.suggestion:
            if "more detailed" in feedback.suggestion.lower() or "more code" in feedback.suggestion.lower():
                self.preferences.response_length = "detailed"
            elif "shorter" in feedback.suggestion.lower() or "concise" in feedback.suggestion.lower():
                self.preferences.response_length = "concise"
            
            if "advanced" in feedback.suggestion.lower():
                self.preferences.technical_depth = "advanced"
            elif "simpler" in feedback.suggestion.lower() or "basic" in feedback.suggestion.lower():
                self.preferences.technical_depth = "basic"
    
    async def invoking(
        self,
        messages: ChatMessage | Sequence[ChatMessage],
        **kwargs: Any
    ) -> Context:
        """
        Inject learned policy as instructions before LLM call.
        This is how the agent acts on what it learned.
        """
        instructions = [
            f"Technical level: provide {self.preferences.technical_depth} explanations.",
            f"Response style: keep responses {self.preferences.response_length}.",
        ]
        
        if self.preferences.prefer_examples:
            instructions.append("Include practical code examples when relevant.")
        
        # Show learning progress
        win_rate = (
            (self.preferences.positive_feedback / self.preferences.feedback_count * 100)
            if self.preferences.feedback_count > 0
            else 0
        )
        print(f"[RL] Policy: depth={self.preferences.technical_depth}, "
              f"length={self.preferences.response_length}, "
              f"feedback={self.preferences.feedback_count}, "
              f"win_rate={win_rate:.0f}%")
        
        return Context(instructions=" ".join(instructions))
    
    def serialize(self) -> str:
        """Save learned preferences for persistence."""
        return self.preferences.model_dump_json()


# ============================================================================
# STEP 3: Create Agent with RL
# ============================================================================

async def create_rl_agent():
    """Create an agent with reinforcement learning capability."""
    
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
    
    chat_client = AzureOpenAIChatClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    )

    # Create RL provider
    rl_provider = PreferenceLearningProvider(chat_client)

    # Create agent
    agent = chat_client.create_agent(
        name="AdaptiveAssistant",
        instructions="You are a helpful assistant that learns from user feedback.",
        context_providers=rl_provider
    )
    
    return agent, rl_provider


# ============================================================================
# EXAMPLE: RL Feedback Loop in Action
# ============================================================================

async def demo_rl_learning():
    """Demonstrate reinforcement learning improving agent over time."""
    
    print("\nRL Feedback Loop: Agent Learning from User Preferences")
    print("=" * 70)
    
    agent, rl_provider = await create_rl_agent()
    thread = agent.get_new_thread()
    
    # Interaction 1: User shows preference for concise responses
    print("\n[Turn 1] User asks: Explain recursion")
    response1 = await agent.run("Explain recursion", thread=thread)
    print(f"Agent: {response1.text[:200]}...")
    print("User feedback: Response too long, I prefer concise explanations")
    await agent.run("Response too long, I prefer concise explanations", thread=thread)
    
    # Interaction 2: Agent should adapt
    print("\n[Turn 2] User asks: What is polymorphism?")
    response2 = await agent.run("What is polymorphism?", thread=thread)
    print(f"Agent: {response2.text[:200]}...")
    print("User feedback: Much better! Keep it concise")
    await agent.run("Much better! Keep it concise", thread=thread)
    
    # Interaction 3: User shows preference for code examples
    print("\n[Turn 3] User asks: How do I use lambda functions?")
    response3 = await agent.run("How do I use lambda functions?", thread=thread)
    print(f"Agent: {response3.text[:200]}...")
    print("User feedback: Good explanation, but I'd like to see more code examples")
    await agent.run("Good explanation, but I'd like to see more code examples", thread=thread)
    
    # Interaction 4: Agent applies multiple learned preferences
    print("\n[Turn 4] User asks: Explain decorators in Python")
    response4 = await agent.run("Explain decorators in Python", thread=thread)
    print(f"Agent: {response4.text[:200]}...")
    print("User feedback: Perfect! Concise with great examples")
    await agent.run("Perfect! Concise with great examples", thread=thread)
    
    # Show final learned policy
    print("\n" + "=" * 70)
    print("Final Learned Policy:")
    print(f"Technical Depth: {rl_provider.preferences.technical_depth}")
    print(f"Response Length: {rl_provider.preferences.response_length}")
    print(f"Include Examples: {rl_provider.preferences.prefer_examples}")
    print(f"Total Feedback: {rl_provider.preferences.feedback_count}")
    print(f"Positive Feedback: {rl_provider.preferences.positive_feedback}")
    if rl_provider.preferences.feedback_count > 0:
        win_rate = rl_provider.preferences.positive_feedback / rl_provider.preferences.feedback_count * 100
        print(f"Win Rate: {win_rate:.0f}%")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Run reinforcement learning demonstration."""
    
    print("\nReinforcement Learning with Microsoft Agent Framework")
    print("=" * 70)
    
    await demo_rl_learning()


if __name__ == "__main__":
    asyncio.run(main())
