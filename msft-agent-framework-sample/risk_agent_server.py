"""
Local A2A Risk Assessment Agent Server

Run: python risk_agent_server.py
URL: http://localhost:8000
"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn

app = FastAPI(title="Risk Assessment A2A Agent")

# Agent Card Definition (served at /.well-known/agent.json)
AGENT_CARD = {
    "name": "risk_assessment_agent",
    "version": "1.0.0",
    "description": "Evaluates customer credit risk and recommends interest rates",
    "url": "http://localhost:8000",
    "capabilities": {
        "assess_risk": {
            "description": "Assess credit risk for a customer",
            "input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "credit_score": {"type": "integer"},
                    "annual_income": {"type": "number"},
                    "loan_amount": {"type": "number"}
                },
                "required": ["customer_id", "credit_score", "annual_income"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "risk_score": {"type": "number"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "recommended_interest_rate": {"type": "number"}
                }
            }
        }
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [
        {
            "id": "assess_risk",
            "name": "assess_risk",
            "description": "Assess credit risk for a customer",
            "tags": ["risk", "assessment"]
        }
    ],
    "endpoints": [
        {
            "path": "/api/assess_risk",
            "method": "POST",
            "description": "Assess risk for a customer"
        }
    ]
}

class RiskRequest(BaseModel):
    customer_id: str
    credit_score: int
    annual_income: float
    existing_debt: Optional[float] = 0
    loan_amount: Optional[float] = 0

class RiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    recommended_interest_rate: float
    recommendation: str

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """A2A Agent Card Discovery Endpoint"""
    return JSONResponse(content=AGENT_CARD)

@app.post("/api/assess_risk")
async def assess_risk(request: RiskRequest) -> RiskResponse:
    """A2A Risk Assessment Handler"""
    
    # Simple risk calculation logic
    risk_score = 0
    
    # Credit score impact (lower is riskier)
    if request.credit_score < 580:
        risk_score += 40
    elif request.credit_score < 670:
        risk_score += 30
    elif request.credit_score < 740:
        risk_score += 15
    elif request.credit_score < 800:
        risk_score += 5
    
    # Debt-to-income ratio impact
    debt_to_income = (request.existing_debt + (request.loan_amount or 0)) / request.annual_income if request.annual_income > 0 else 1.0
    if debt_to_income > 0.5:
        risk_score += 30
    elif debt_to_income > 0.35:
        risk_score += 15
    elif debt_to_income > 0.25:
        risk_score += 5
    
    # Determine risk level
    if risk_score >= 70:
        risk_level = "high"
        interest_rate = 8.5
        recommendation = "REJECT - High credit risk"
    elif risk_score >= 50:
        risk_level = "medium"
        interest_rate = 6.5
        recommendation = "CONDITIONAL - Requires additional review"
    else:
        risk_level = "low"
        interest_rate = 4.5
        recommendation = "APPROVE - Low credit risk"
    
    return RiskResponse(
        risk_score=min(100, risk_score),
        risk_level=risk_level,
        recommended_interest_rate=interest_rate,
        recommendation=recommendation
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "agent": "risk_assessment_agent"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
