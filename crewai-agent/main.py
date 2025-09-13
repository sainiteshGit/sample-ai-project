import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

llm = LLM(
    model="azure/" + os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
    temperature=0.1,
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"))

# Daily Planner AI Agent
planner_agent = Agent(
    role='Daily Planner AI',
    goal='Create personalized daily schedules, set priorities, and provide helpful reminders',
    backstory="""You are an expert personal assistant with years of experience in time management 
    and productivity. You understand how to balance work, personal life, and self-care. You create 
    realistic schedules that account for travel time, breaks, and unexpected interruptions.""",
    llm=llm,
    verbose=True
)

def get_user_input():
    """Collect essential user input for daily planning"""
    print("🗓️ Welcome to your Daily Planner AI!")
    print("="*40)
    
    # Get user's name
    name = input("What's your name? ").strip() or "there"
    
    # Get tasks/activities
    print(f"\nHi {name}! What do you need to get done today?")
    print("List your tasks separated by commas:")
    
    tasks_input = input("Tasks: ").strip()
    tasks = [task.strip() for task in tasks_input.split(',') if task.strip()]
    
    if not tasks:
        tasks = ["Check emails", "Work on projects", "Take a break"]
    
    return {
        'name': name,
        'tasks': tasks
    }

def create_planning_task(user_input):
    """Create a concise planning task based on user input"""
    tasks_list = ", ".join(user_input['tasks'])
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    description = f"""Create a simple daily plan for {user_input['name']} on {today}.

Tasks to schedule: {tasks_list}

Create a concise plan with EXACTLY 10 bullet points that includes:
- Time blocks for each task
- Priorities (High/Medium/Low)
- Short breaks
- Meal times
- One productivity tip

Keep each bullet point short and actionable. Format as a numbered list from 1-10."""

    return Task(
        description=description,
        expected_output=f"""A concise 10-point daily schedule for {user_input['name']} with specific times, priorities, and one helpful tip. Each point should be one line only.""",
        agent=planner_agent
    )

# Main execution
if __name__ == "__main__":
    # Get user input
    user_data = get_user_input()
    
    # Create personalized task
    planning_task = create_planning_task(user_data)
    
    # Create a crew with the planner agent
    crew = Crew(
        agents=[planner_agent],
        tasks=[planning_task],
        verbose=True
    )
    
    # Execute the daily planning task
    print(f"\n Creating your 10-point plan, {user_data['name']}...\n")
    result = crew.kickoff()
    
    print("\n" + "="*50)
    print(f"📋 {user_data['name'].upper()}'S DAILY PLAN")
    print("="*50)
    print(result)
    print("\n✨ Have a productive day!")
