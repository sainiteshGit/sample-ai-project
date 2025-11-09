"""
Vision Agent Demo - Using Images with Agents
Blog: "Seeing What AI Sees: Using Images with Agents"

Demonstrates:
- Analyzing images from URLs
- Processing local image files
- Document inspection and data extraction
"""

import os
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import ChatMessage, TextContent, UriContent, DataContent, Role

# Sample image URL for testing
SAMPLE_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"


async def analyze_image_from_url(agent, image_url: str, prompt: str):
    """Analyze an image from a URL"""
    print(f"🔍 {prompt}")
    
    message = ChatMessage(
        role=Role.USER,
        contents=[
            TextContent(text=prompt),
            UriContent(uri=image_url, media_type="image/jpeg")
        ]
    )
    
    result = await agent.run(message)
    print(f" {result.text}\n")


async def analyze_local_image(agent, image_path: str, prompt: str):
    """Analyze a local image file"""
    if not os.path.exists(image_path):
        print(f" Image not found: {image_path}")
        return
    
    print(f"🔍 {prompt} ({os.path.basename(image_path)})")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    ext = os.path.splitext(image_path)[1].lower()
    media_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}
    media_type = media_types.get(ext, 'image/jpeg')
    
    message = ChatMessage(
        role=Role.USER,
        contents=[
            TextContent(text=prompt),
            DataContent(data=image_bytes, media_type=media_type)
        ]
    )
    
    result = await agent.run(message)
    print(f"📋 {result.text}\n")


async def main():
    print("\nVision Agent Demo")
    print("=" * 50)
    
    # Load credentials
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        raise ValueError("Azure OpenAI environment variables required")
    
    print(f"Using deployment: {deployment}")
    
    # Create vision agent
    try:
        chat_client = AzureOpenAIChatClient(
            endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment
        )
        
        agent = chat_client.create_agent(
            name="VisionAgent",
            instructions="You are a helpful vision agent that analyzes images and extracts information."
        )
        
        # Demo 1: Image from URL
        print("\n1. Analyze Image from URL")
        await analyze_image_from_url(
            agent,
            SAMPLE_IMAGE_URL,
            "Describe this scene briefly."
        )
        
        # Demo 2: Local image (if available)
        print("2. Analyze Local Image")
        local_images = list(Path(".").glob("*.jpg")) + list(Path(".").glob("*.png"))
        if local_images:
            await analyze_local_image(
                agent,
                str(local_images[0]),
                "What is in this image?"
            )
        else:
            print(" No local images found\n")
        
        print("=" * 50)
        print(" Done!\n")
        
    except Exception as e:
        print(f"\nError: {str(e)[:200]}")
        print("\n💡 Common issues:")
        print("   • Deployment not found (404): Check AZURE_OPENAI_DEPLOYMENT")
        print("   • Must use vision-capable model: gpt-4o, gpt-4-vision-preview, gpt-4-turbo")
        print(f"   • Current deployment: {deployment}")
        print("   • Verify the deployment exists in your Azure OpenAI resource")
        raise


if __name__ == "__main__":
    asyncio.run(main())
