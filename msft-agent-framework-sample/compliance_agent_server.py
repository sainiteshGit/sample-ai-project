"""
Local A2A Compliance Verification Agent Server

Run: python compliance_agent_server.py
URL: http://localhost:8001
"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn

app = FastAPI(title="Compliance Verification A2A Agent")

# Agent Card Definition (served at /.well-known/agent.json)
AGENT_CARD = {
    "name": "compliance_agent",
    "version": "1.0.0",
    "description": "Verifies regulatory compliance and sanctions checks",
    "url": "http://localhost:8001",
    "capabilities": {
        "verify_compliance": {
            "description": "Verify customer compliance and regulatory requirements",
            "input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["customer_id", "customer_name"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pass", "fail", "review_required"]},
                    "sanctions_check": {"type": "string"},
                    "aml_check": {"type": "string"},
                    "flags": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [
        {
            "id": "verify_compliance",
            "name": "verify_compliance",
            "description": "Verify customer compliance and regulatory requirements",
            "tags": ["compliance", "aml", "kyc"]
        }
    ],
    "endpoints": [
        {
            "path": "/api/verify_compliance",
            "method": "POST",
            "description": "Verify customer compliance"
        }
    ]
}

class ComplianceRequest(BaseModel):
    customer_id: str
    customer_name: str
    customer_country: Optional[str] = "US"
    loan_amount: Optional[float] = 0

class ComplianceResponse(BaseModel):
    status: str
    sanctions_check: str
    aml_check: str
    kyc_status: str
    flags: List[str]
    recommendation: str

# Mock sanctions list
SANCTIONS_LIST = {"iran", "north korea", "syria", "cuba"}

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """A2A Agent Card Discovery Endpoint"""
    return JSONResponse(content=AGENT_CARD)

@app.post("/api/verify_compliance")
async def verify_compliance(request: ComplianceRequest) -> ComplianceResponse:
    """A2A Compliance Verification Handler"""
    
    flags = []
    status = "pass"
    
    # Sanctions check
    if request.customer_country and request.customer_country.lower() in SANCTIONS_LIST:
        flags.append(f"Customer country {request.customer_country} is on sanctions list")
        status = "fail"
    
    sanctions_check = "CLEAR" if not any("sanctions" in f.lower() for f in flags) else "BLOCKED"
    
    # AML (Anti-Money Laundering) check
    aml_check = "PASS"
    if request.loan_amount and request.loan_amount > 100000:
        flags.append("Large transaction - enhanced due diligence required")
        if status == "pass":
            status = "review_required"
    
    # KYC (Know Your Customer) check
    kyc_status = "VERIFIED"
    if not request.customer_name or len(request.customer_name.split()) < 2:
        flags.append("Incomplete customer name - KYC verification required")
        kyc_status = "PENDING"
        if status == "pass":
            status = "review_required"
    
    # Determine recommendation
    if status == "fail":
        recommendation = "REJECT - Compliance violation detected"
    elif status == "review_required":
        recommendation = "CONDITIONAL - Manual compliance review required"
    else:
        recommendation = "APPROVE - All compliance checks passed"
    
    return ComplianceResponse(
        status=status,
        sanctions_check=sanctions_check,
        aml_check=aml_check,
        kyc_status=kyc_status,
        flags=flags,
        recommendation=recommendation
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "agent": "compliance_agent"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
