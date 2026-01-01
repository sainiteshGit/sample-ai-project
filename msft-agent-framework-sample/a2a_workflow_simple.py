import os
import asyncio
import json
import re
from dataclasses import dataclass
import httpx

from agent_framework.azure import AzureOpenAIChatClient
from a2a.client import A2ACardResolver

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class CustomerProfile:
    customer_id: str
    name: str
    age: int
    annual_income: float
    credit_score: int
    loan_request_amount: float
    existing_debt: float = 0.0


async def create_a2a_agents(http_client):
    configs = {
        "risk_assessment_agent": {"base_url": "http://localhost:8000"},
        "compliance_agent": {"base_url": "http://localhost:8001"}
    }
    
    for agent_id, urls in configs.items():
        try:
            resolver = A2ACardResolver(httpx_client=http_client, base_url=urls["base_url"])
            await resolver.get_agent_card(relative_card_path="/.well-known/agent.json")
            print(f"✓ Discovered {agent_id}")
        except:
            print(f"⚠ Failed: {agent_id}")


async def process_customer(chat_client, customer):
    risk_data = {"risk_level": "medium", "recommended_interest_rate": 6.5}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/assess_risk",
                json={
                    "customer_id": customer.customer_id,
                    "credit_score": customer.credit_score,
                    "annual_income": customer.annual_income,
                    "existing_debt": customer.existing_debt,
                    "loan_amount": customer.loan_request_amount
                }
            )
            risk_data = response.json() if response.status_code == 200 else risk_data
    except:
        pass
    
    compliance_data = {"status": "pass"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8001/api/verify_compliance",
                json={
                    "customer_id": customer.customer_id,
                    "customer_name": customer.name,
                    "customer_country": "US",
                    "loan_amount": customer.loan_request_amount
                }
            )
            compliance_data = response.json() if response.status_code == 200 else compliance_data
    except:
        pass
    
    agent = chat_client.create_agent(
        name="LoanOfficer",
        instructions="Make decision with JSON: {approved, loan_amount, interest_rate}"
    )
    
    prompt = f"Loan for {customer.name}: ${customer.annual_income:,.0f} income, ${customer.loan_request_amount:,.0f} request"
    response = await agent.run(prompt)
    
    try:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        return json.loads(match.group()) if match else {"approved": True, "loan_amount": customer.loan_request_amount * 0.8, "interest_rate": 6.5}
    except:
        return {"approved": True, "loan_amount": customer.loan_request_amount * 0.8, "interest_rate": 6.5}


async def main():
    chat_client = AzureOpenAIChatClient(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version="2024-10-21"
    )
    
    customers = [
        CustomerProfile("C001", "Alice Johnson", 35, 50000, 750, 40000),
        CustomerProfile("C002", "Bob Smith", 42, 35000, 680, 30000)
    ]
    
    async with httpx.AsyncClient() as http_client:
        print("📡 Discovering A2A agents...")
        await create_a2a_agents(http_client)
    
    for customer in customers:
        decision = await process_customer(chat_client, customer)
        approved = " APPROVED" if decision.get("approved") else " REJECTED"
        amount = f"${decision.get('loan_amount', 0):,.0f}"
        rate = decision.get("interest_rate", 0)
        print(f"{customer.name}: {approved} - {amount} @ {rate}%")


if __name__ == "__main__":
    asyncio.run(main())
