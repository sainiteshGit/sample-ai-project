"""
Structured Output Example: Automated Code Review
Demonstrates how to produce predictable, validated output using Microsoft Agent Framework
"""

import asyncio
import os
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from dotenv import load_dotenv

from agent_framework.azure import AzureOpenAIChatClient

# Load environment variables
load_dotenv()


# ============================================================================
# STEP 1: Define Your Schema
# ============================================================================

class CodeIssue(BaseModel):
    """A single code issue found during review."""
    category: Literal["security", "performance", "quality", "best-practice"]
    severity: Literal["low", "medium", "high", "critical"]
    line_number: Optional[int] = Field(None, description="Line number where issue occurs")
    description: str = Field(..., description="Description of the issue")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class CodeReview(BaseModel):
    """Structured code review results."""
    overall_quality: Literal["excellent", "good", "fair", "poor"]
    issues: List[CodeIssue] = Field(default_factory=list, description="List of issues found")
    positive_points: List[str] = Field(default_factory=list, description="Good aspects of the code")
    needs_refactoring: bool = Field(False, description="Whether code needs refactoring")


# ============================================================================
# STEP 2: Create the Agent
# ============================================================================

async def create_code_reviewer():
    """Create an agent that reviews code with structured output."""
    
    # Get Azure OpenAI configuration from environment
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
    
    agent = AzureOpenAIChatClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    ).create_agent(
        name="CodeReviewer",
        instructions="""You are an expert code reviewer. Analyze code for:
        - Security vulnerabilities (SQL injection, XSS, etc.)
        - Performance issues (inefficient loops, memory leaks)
        - Code quality (readability, maintainability)
        - Best practices (error handling, input validation)
        
        Be thorough but constructive."""
    )
    
    return agent


# ============================================================================
# STEP 3: Review Code with Structured Output
# ============================================================================

async def review_code(agent, code: str) -> Optional[CodeReview]:
    """
    Analyze code and return structured review.
    
    Args:
        agent: The ChatClientAgent instance
        code: Source code to review
        
    Returns:
        CodeReview object with structured feedback, or None if review fails
    """
    
    response = await agent.run(
        f"Review this Python code and provide detailed feedback:\n\n{code}",
        response_format=CodeReview  # ← This enforces structured output
    )
    
    return response.value


# ============================================================================
# EXAMPLE: Code Review with Security Vulnerability
# ============================================================================

async def demo_code_review():
    """Review code with SQL injection vulnerability."""
    
    print("\n" + "=" * 70)
    print("EXAMPLE: Automated Code Review with Structured Output")
    print("=" * 70)
    
    code_to_review = '''
def get_user_data(user_id):
    # Fetch user from database
    query = f"SELECT * FROM users WHERE id = {user_id}"
    result = db.execute(query)
    
    # Process data
    data = []
    for row in result:
        data.append({
            'id': row[0],
            'name': row[1],
            'email': row[2]
        })
    
    return data
'''
    
    print("\n📝 Code to Review:")
    print(code_to_review)
    
    # Create agent and review
    agent = await create_code_reviewer()
    review = await review_code(agent, code_to_review)
    
    if review:
        print(f"\n✅ Structured Review Results:")
        print(f"   Overall Quality: {review.overall_quality.upper()}")
        print(f"   Needs Refactoring: {'Yes' if review.needs_refactoring else 'No'}")
        
        if review.positive_points:
            print(f"\n✨ Positive Points:")
            for point in review.positive_points:
                print(f"   + {point}")
        
        if review.issues:
            print(f"\n🔍 Issues Found ({len(review.issues)}):")
            for i, issue in enumerate(review.issues, 1):
                severity_emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }
                emoji = severity_emoji.get(issue.severity, "⚪")
                
                print(f"\n   {i}. {emoji} [{issue.severity.upper()}] {issue.category.replace('-', ' ').title()}")
                if issue.line_number:
                    print(f"      Line: {issue.line_number}")
                print(f"      Issue: {issue.description}")
                if issue.suggestion:
                    print(f"      💡 Fix: {issue.suggestion}")
    else:
        print(f"\n❌ Failed to review code")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Run code review demonstration."""
    
    print("\n" + "🎯" * 35)
    print("STRUCTURED OUTPUT: AUTOMATED CODE REVIEW")
    print("🎯" * 35)
    
    print("\n📚 How It Works:")
    print("=" * 70)
    print("1. Define CodeReview schema with Pydantic")
    print("2. Create ChatClientAgent with Azure OpenAI")
    print("3. Call agent.run() with response_format=CodeReview")
    print("4. Receive validated CodeReview object - no parsing!")
    print("=" * 70)
    
    await demo_code_review()
    
    print("\n" + "=" * 70)
    print("✨ KEY TAKEAWAYS")
    print("=" * 70)
    print("✓ Consistent structure for every code review")
    print("✓ Type-safe access to issues, severity, suggestions")
    print("✓ No manual parsing or regex required")
    print("✓ Ready for CI/CD integration, dashboards, alerts")
    print("✓ Easy filtering: review.issues by severity or category")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

