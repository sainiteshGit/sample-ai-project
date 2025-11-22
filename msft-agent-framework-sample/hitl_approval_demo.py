"""
Human-in-the-Loop Approval Demo - Function Tools with Approvals
"""

import os
import asyncio

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent_framework.azure import AzureOpenAIChatClient


def process_payment(amount: float, recipient: str, description: str) -> str:
    """Simulate payment processing."""
    print(f"\n💳 PAYMENT PROCESSED")
    print(f"   Amount: ${amount:,.2f}")
    print(f"   Recipient: {recipient}")
    print(f"   Description: {description}")
    print(f"✅ Transaction completed successfully!\n")
    return f"Payment of ${amount:,.2f} to {recipient} processed successfully"


def get_approval(amount: float, recipient: str, description: str) -> tuple[bool, str]:
    """Get human approval for payment."""
    print(f"\n{'='*70}")
    print(f"🔔 APPROVAL REQUEST")
    print(f"{'='*70}")
    print(f"Function: process_payment")
    print(f"\nDetails:")
    print(f"  💰 Amount: ${amount:,.2f}")
    print(f"  👤 Recipient: {recipient}")
    print(f"  📝 Description: {description}")
    print(f"{'='*70}")
    
    while True:
        user_input = input("\n👤 Approve this payment? (yes/no): ").strip().lower()
        if user_input == "yes":
            print("✅ APPROVED - Processing payment...")
            return True, ""
        elif user_input == "no":
            reason = input("📝 Reason for rejection (optional): ").strip()
            print("❌ REJECTED - Payment canceled")
            return False, reason or "User rejected the payment."
        else:
            print("⚠️  Please enter 'yes' or 'no'")


async def demo1_payment_with_approval():
    """Demo 1: Payment Processing with Human Approval"""
    print("\n" + "="*70)
    print("DEMO 1: Payment Assistant with Human-in-the-Loop Approval")
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
        name="PaymentAssistant",
        instructions="""You are a helpful payment assistant. 
        When processing payments, extract the amount, recipient, and purpose.
        Keep responses concise and professional."""
    )
    
    thread = agent.get_new_thread()
    
    print("\n👤 User: Pay $2,500 to Acme Suppliers for the office furniture invoice")
    response1 = await agent.run(
        "Pay $2,500 to Acme Suppliers for the office furniture invoice",
        thread=thread
    )
    print(f"\n🤖 Agent: {response1}\n")
    
    # Human-in-the-loop approval checkpoint
    approved, feedback = get_approval(2500, "Acme Suppliers", "Office furniture invoice")
    
    if approved:
        result = process_payment(2500, "Acme Suppliers", "Office furniture invoice")
        response2 = await agent.run(
            f"The payment has been approved and processed. {result}",
            thread=thread
        )
        print(f"🤖 Agent: {response2}\n")
    else:
        response2 = await agent.run(
            f"The payment was rejected. Reason: {feedback}",
            thread=thread
        )
        print(f"🤖 Agent: {response2}\n")


async def demo2_payment_with_rejection():
    """Demo 2: Payment Rejection Scenario"""
    print("\n" + "="*70)
    print("DEMO 2: Payment Rejection Handling")
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
        name="PaymentAssistant",
        instructions="""You are a helpful payment assistant.
        If a payment is rejected, be professional and suggest next steps.
        Keep responses concise."""
    )
    
    thread = agent.get_new_thread()
    
    print("\n👤 User: Send $5,000 payment to Global Tech Inc for software licenses")
    response1 = await agent.run(
        "Send $5,000 payment to Global Tech Inc for software licenses",
        thread=thread
    )
    print(f"\n🤖 Agent: {response1}\n")
    
    # Simulate automatic rejection (exceeds limit)
    print("🔔 APPROVAL REQUEST")
    print("   Function: process_payment")
    print("   Amount: $5,000.00")
    print("   Recipient: Global Tech Inc")
    print("\n❌ AUTO-REJECTED - Amount exceeds daily limit of $2,000\n")
    
    response2 = await agent.run(
        "The payment was rejected because it exceeds your daily transaction limit of $2,000. Manager approval is required for payments above this amount.",
        thread=thread
    )
    print(f"🤖 Agent: {response2}\n")
    
    print("✅ Agent handled rejection professionally!")



async def main():
    print("\nHUMAN-IN-THE-LOOP APPROVAL DEMO")
    print("="*70)
    
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        raise ValueError("Azure OpenAI environment variables required")
    
    print(f"Using deployment: {deployment}")
    
    await demo1_payment_with_approval()
    await demo2_payment_with_rejection()
    
    print("\n✅ DEMO COMPLETE\n")


if __name__ == "__main__":
    asyncio.run(main())
