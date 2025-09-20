import os
from agents import Agent, OpenAIChatCompletionsModel, set_tracing_disabled, function_tool
from agents import Runner
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

# Load environment variables from .env file
load_dotenv()

# Disable tracing to prevent non-fatal error messages about OpenAI API key
set_tracing_disabled(True)
# Configure environment variables for openai-agents library to work with Azure OpenAI
os.environ["OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_KEY")
# For Azure OpenAI, the base URL should point to the Azure OpenAI endpoint
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
os.environ["OPENAI_BASE_URL"] = azure_endpoint
# Set additional Azure-specific environment variables
os.environ["OPENAI_API_TYPE"] = "azure"



openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  # Note: Using subscription key
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15"),  # Default to a common version if not set
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT")
)

model=OpenAIChatCompletionsModel(
            model="gpt-4.1", # This will use the deployment specified in your Azure OpenAI/APIM client
            openai_client=openai_client
        )


# --- Tool 1: Calendar Summary ---
@function_tool
def get_calendar_summary() -> str:
    return "You have 2 meetings today: 10 AM sync and 2 PM design review."

schedule_agent = Agent(
    name="ScheduleAgent",
    instructions="Summarize today's calendar events.",
    tools=[get_calendar_summary],
    model=model  # Use your deployed Azure model name
)

# --- Tool 2: Meal Suggestion ---
@function_tool
def suggest_meal(fridge_items: str) -> str:
    return f"Based on your fridge items ({fridge_items}), I suggest a spinach omelette and oats."

meal_agent = Agent(
    name="MealAgent",
    instructions="Suggest a healthy breakfast based on fridge contents.",
    tools=[suggest_meal],
    model=model
)

# --- Tool 3: Health Reminder ---
@function_tool
def health_check(sleep_hours: float) -> str:
    if sleep_hours < 7:
        return "You slept 6.5 hours. Drink water and stretch for 5 minutes."
    else:
        return "You slept well. Stay hydrated and take a short walk later."

health_agent = Agent(
    name="HealthAgent",
    instructions="Give hydration and movement reminders based on sleep.",
    tools=[health_check],
    model=model
)


@function_tool
def synthesize_plan(calendar: str, meal: str, health: str) -> str:
    return (
        f"Here's your plan:\n"
        f"- Calendar: {calendar}\n"
        f"- Meal: {meal}\n"
        f"- Health: {health}"
    )

planner_agent = Agent(
    name="PlannerAgent",
    instructions="Combine calendar, meal, and health info into a daily plan.",
    tools=[synthesize_plan],
    model=model
)

calendar_output = Runner.run_sync(schedule_agent, "What's on my calendar today?").final_output
meal_output = Runner.run_sync(meal_agent, "Fridge items: eggs, spinach, oats").final_output
health_output = Runner.run_sync(health_agent, "I slept 6.5 hours").final_output

final_plan = Runner.run_sync(
    planner_agent,
    f"calendar: {calendar_output}\nmeal: {meal_output}\nhealth: {health_output}"
)

print("🧠 Final Daily Plan:\n", final_plan.final_output)

