"""
Morning Routine AI Agent Workflow - Microsoft Agent Framework Example
===================================================================

This example demonstrates a real-world morning routine workflow using actual Azure AI agents
with Microsoft Agent Framework. Perfect for early career developers learning about AI agent
orchestration in daily life scenarios.

Scenario: Personalized morning routine planning with AI agents
Based on the official Microsoft Agent Framework patterns from content_pipeline_workflow.py
"""

import os
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from agent_framework import (
    Executor, 
    WorkflowBuilder, 
    WorkflowContext, 
    handler,
    WorkflowOutputEvent
)
from agent_framework.azure import AzureOpenAIResponsesClient

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@dataclass
class PersonProfile:
    """Represents a person's profile and preferences"""
    name: str
    work_start_time: str
    preferences: List[str]
    location: str
    fitness_level: str = "moderate"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class MorningPlan:
    """Represents a morning routine plan at different stages"""
    person_name: str
    weather_analysis: str = ""
    schedule_analysis: str = ""
    routine_steps: List[str] = None
    optimization_notes: str = ""
    final_timeline: str = ""
    status: str = "initial"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.routine_steps is None:
            self.routine_steps = []
        if self.metadata is None:
            self.metadata = {}

class WeatherAnalystExecutor(Executor):
    """
    First stage: Weather analysis and clothing recommendations
    
    This AI agent analyzes weather conditions and provides practical advice
    for morning routine planning including clothing and activity recommendations.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        # Create a specialized weather analysis agent
        self.responses_client = responses_client
        super().__init__(id="weather_analyst")
    
    @handler
    async def analyze_weather(self, profile: PersonProfile, ctx: WorkflowContext[MorningPlan]) -> None:
        print(f"Analyzing weather for {profile.name} in {profile.location}...")
        
        # Prepare the weather analysis prompt
        prompt = f"""
        Analyze weather conditions and provide morning routine advice for:
        
        Person: {profile.name}
        Location: {profile.location}
        Work Start Time: {profile.work_start_time}
        Preferences: {', '.join(profile.preferences)}
        Fitness Level: {profile.fitness_level}
        
        Please provide:
        1. Current weather summary for this morning
        2. Clothing recommendations with layers
        3. Indoor/outdoor activity suggestions
        4. Commute and transportation advice
        5. Any special considerations for the morning routine
        
        Format your response as practical, actionable advice.
        """
        
        try:
            # Create agent on demand and get weather analysis
            agent = self.responses_client.create_agent(
                name="WeatherAnalyst",
                instructions="You are an expert weather analyst and lifestyle advisor. Provide practical weather advice for morning routines including clothing, activities, and transportation considerations."
            )
            response = await agent.run(prompt)
            weather_analysis = response.text
            
            # Create initial morning plan with weather analysis
            morning_plan = MorningPlan(
                person_name=profile.name,
                weather_analysis=weather_analysis,
                status="weather_analyzed",
                metadata={
                    "location": profile.location,
                    "work_start_time": profile.work_start_time,
                    "preferences": profile.preferences,
                    "fitness_level": profile.fitness_level
                }
            )
            
            print("Weather analysis completed")
            await ctx.send_message(morning_plan)
            
        except Exception as e:
            print(f"Weather analysis failed: {e}")
            # Send initial plan with error flag
            error_plan = MorningPlan(
                person_name=profile.name,
                weather_analysis=f"Weather analysis error: {e}",
                status="weather_error",
                metadata={"error": str(e)}
            )
            await ctx.send_message(error_plan)

class ScheduleAnalyzerExecutor(Executor):
    """
    Second stage: Calendar and schedule analysis
    
    This AI agent analyzes the person's daily schedule and work commitments
    to determine optimal morning routine timing and priorities.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="schedule_analyzer")
    
    @handler
    async def analyze_schedule(self, plan: MorningPlan, ctx: WorkflowContext[MorningPlan]) -> None:
        print(f"Analyzing schedule and commitments for {plan.person_name}...")
        
        if plan.status not in ["weather_analyzed"]:
            print("Skipping schedule analysis - weather analysis incomplete")
            await ctx.send_message(plan)
            return
        
        # Extract work start time from metadata
        work_start_time = plan.metadata.get("work_start_time", "9:00 AM")
        preferences = plan.metadata.get("preferences", [])
        
        prompt = f"""
        Analyze the schedule and create timing recommendations:
        
        Person: {plan.person_name}
        Work Start Time: {work_start_time}
        Preferences: {', '.join(preferences)}
        Weather Considerations: {plan.weather_analysis[:200]}...
        
        Create a schedule analysis that includes:
        1. Optimal wake-up time calculation
        2. Time allocation for morning activities
        3. Buffer time recommendations
        4. Priority ranking of morning tasks
        5. Flexibility suggestions for busy vs. light days
        
        Consider commute time, personal care, breakfast, exercise preferences, and any prep work needed.
        Provide specific time recommendations and explain the reasoning.
        """
        
        try:
            agent = self.responses_client.create_agent(
                name="ScheduleAnalyzer",
                instructions="You are an expert time management and scheduling advisor. Analyze daily schedules and provide optimal timing recommendations for morning routines."
            )
            response = await agent.run(prompt)
            schedule_analysis = response.text
            
            # Update the morning plan with schedule analysis
            updated_plan = MorningPlan(
                person_name=plan.person_name,
                weather_analysis=plan.weather_analysis,
                schedule_analysis=schedule_analysis,
                status="schedule_analyzed",
                metadata=plan.metadata
            )
            
            print("Schedule analysis completed")
            await ctx.send_message(updated_plan)
            
        except Exception as e:
            print(f"Schedule analysis failed: {e}")
            error_plan = MorningPlan(
                person_name=plan.person_name,
                weather_analysis=plan.weather_analysis,
                schedule_analysis=f"Schedule analysis error: {e}",
                status="schedule_error",
                metadata={**plan.metadata, "schedule_error": str(e)}
            )
            await ctx.send_message(error_plan)

class RoutinePlannerExecutor(Executor):
    """
    Third stage: Detailed routine planning
    
    This AI agent creates specific, actionable morning routine steps
    based on weather analysis and schedule constraints.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="routine_planner")
    
    @handler
    async def plan_routine(self, plan: MorningPlan, ctx: WorkflowContext[MorningPlan]) -> None:
        print(f"Creating detailed routine plan for {plan.person_name}...")
        
        if plan.status != "schedule_analyzed":
            print("Skipping routine planning - schedule analysis incomplete")
            await ctx.send_message(plan)
            return
        
        prompt = f"""
        Create a detailed morning routine plan:
        
        Person: {plan.person_name}
        Weather Analysis: {plan.weather_analysis[:300]}...
        Schedule Analysis: {plan.schedule_analysis[:300]}...
        
        Create a step-by-step morning routine that includes:
        1. Specific wake-up time
        2. Detailed activity sequence with time estimates
        3. Weather-appropriate clothing and preparation
        4. Healthy breakfast options
        5. Exercise or movement activities
        6. Work preparation tasks
        7. Buffer time and flexibility options
        
        Format as a numbered list of activities with time stamps.
        Make it practical, achievable, and personalized.
        """
        
        try:
            agent = self.responses_client.create_agent(
                name="RoutinePlanner",
                instructions="You are an expert morning routine specialist. Create detailed, personalized morning routine plans with specific timing and activities."
            )
            response = await agent.run(prompt)
            routine_content = response.text
            
            # Parse routine steps (simplified parsing)
            routine_steps = []
            for line in routine_content.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or '-' in line or '•' in line):
                    routine_steps.append(line)
            
            planned_routine = MorningPlan(
                person_name=plan.person_name,
                weather_analysis=plan.weather_analysis,
                schedule_analysis=plan.schedule_analysis,
                routine_steps=routine_steps,
                optimization_notes=routine_content,
                status="routine_planned",
                metadata=plan.metadata
            )
            
            print("Routine planning completed")
            await ctx.send_message(planned_routine)
            
        except Exception as e:
            print(f"Routine planning failed: {e}")
            error_plan = MorningPlan(
                person_name=plan.person_name,
                weather_analysis=plan.weather_analysis,
                schedule_analysis=plan.schedule_analysis,
                status="routine_error",
                metadata={**plan.metadata, "routine_error": str(e)}
            )
            await ctx.send_message(error_plan)

class TimelineOptimizerExecutor(Executor):
    """
    Fourth stage: Timeline optimization and final formatting
    
    This AI agent takes the planned routine and optimizes the timeline
    for maximum efficiency and creates a final, easy-to-follow schedule.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="timeline_optimizer")
    
    @handler
    async def optimize_timeline(self, plan: MorningPlan, ctx: WorkflowContext[MorningPlan]) -> None:
        print(f"Optimizing timeline for {plan.person_name}...")
        
        if plan.status != "routine_planned":
            print("Skipping timeline optimization - routine planning incomplete")
            await ctx.send_message(plan)
            return
        
        prompt = f"""
        Optimize the morning routine timeline:
        
        Person: {plan.person_name}
        Planned Routine: {plan.optimization_notes[:500]}...
        
        Create an optimized timeline that:
        1. Identifies parallel activities (things that can be done simultaneously)
        2. Minimizes transitions and wasted time
        3. Includes realistic buffer time
        4. Provides alternatives for rushed mornings
        5. Creates a clean, formatted final schedule
        
        Format the final timeline as:
        - Clear time stamps (e.g., 6:30 AM - 6:45 AM)
        - Specific activities with duration
        - Parallel activity suggestions
        - Quick alternatives for busy days
        - Total routine duration
        
        Make it actionable and easy to follow.
        """
        
        try:
            agent = self.responses_client.create_agent(
                name="TimelineOptimizer",
                instructions="You are an expert efficiency and time management specialist. Optimize morning routines for maximum efficiency, parallel activities, and time savings."
            )
            response = await agent.run(prompt)
            optimized_timeline = response.text
            
            optimized_plan = MorningPlan(
                person_name=plan.person_name,
                weather_analysis=plan.weather_analysis,
                schedule_analysis=plan.schedule_analysis,
                routine_steps=plan.routine_steps,
                optimization_notes=plan.optimization_notes,
                final_timeline=optimized_timeline,
                status="timeline_optimized",
                metadata=plan.metadata
            )
            
            print("Timeline optimization completed")
            await ctx.send_message(optimized_plan)
            
        except Exception as e:
            print(f"Timeline optimization failed: {e}")
            error_plan = MorningPlan(
                person_name=plan.person_name,
                weather_analysis=plan.weather_analysis,
                schedule_analysis=plan.schedule_analysis,
                routine_steps=plan.routine_steps,
                optimization_notes=plan.optimization_notes,
                final_timeline=f"Timeline optimization error: {e}",
                status="timeline_error",
                metadata={**plan.metadata, "timeline_error": str(e)}
            )
            await ctx.send_message(error_plan)

class RoutineFinalizerExecutor(Executor):
    """
    Final stage: Finalize and deliver the morning routine
    
    This executor packages the complete morning routine with all insights
    and delivers the final personalized plan.
    """
    
    def __init__(self):
        super().__init__(id="routine_finalizer")
    
    @handler
    async def finalize_routine(self, plan: MorningPlan, ctx: WorkflowContext[Dict[str, Any]]) -> None:
        print(f"Finalizing morning routine for {plan.person_name}...")
        
        if plan.status != "timeline_optimized":
            print("Cannot finalize - timeline optimization incomplete")
            result = {
                "status": "failed",
                "reason": f"Plan status is {plan.status}, expected 'timeline_optimized'",
                "person_name": plan.person_name
            }
            await ctx.yield_output(result)
            return
        
        # Prepare final routine package
        routine_package = {
            "status": "completed",
            "person_name": plan.person_name,
            "location": plan.metadata.get("location", "Unknown"),
            "work_start_time": plan.metadata.get("work_start_time", "9:00 AM"),
            "preferences": plan.metadata.get("preferences", []),
            "weather_insights": plan.weather_analysis[:200] + "..." if len(plan.weather_analysis) > 200 else plan.weather_analysis,
            "schedule_insights": plan.schedule_analysis[:200] + "..." if len(plan.schedule_analysis) > 200 else plan.schedule_analysis,
            "routine_steps": plan.routine_steps,
            "final_timeline": plan.final_timeline,
            "total_components": {
                "weather_analysis": len(plan.weather_analysis) > 0,
                "schedule_analysis": len(plan.schedule_analysis) > 0,
                "routine_steps": len(plan.routine_steps),
                "timeline_optimized": len(plan.final_timeline) > 0
            },
            "created_at": "2024-12-10T06:00:00Z",
            "metadata": plan.metadata
        }
        
        print(f"Morning routine finalized for {plan.person_name}")
        print(f"Generated {len(plan.routine_steps)} routine steps")
        
        # Yield the final output
        await ctx.yield_output(routine_package)

async def create_morning_routine_workflow():
    """
    Creates and returns the complete morning routine AI agent workflow
    """
    print("Setting up Morning Routine AI Agent Workflow...")
    
    # Initialize Azure OpenAI client using the same pattern as main.py
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is required") 
    if not deployment:
        raise ValueError("AZURE_OPENAI_DEPLOYMENT environment variable is required")
    
    # Create Azure OpenAI Responses client
    responses_client = AzureOpenAIResponsesClient(
        endpoint=endpoint, 
        api_key=api_key, 
        deployment_name=deployment
    )
    
    # Create all AI agent executors
    weather_analyst = WeatherAnalystExecutor(responses_client)
    schedule_analyzer = ScheduleAnalyzerExecutor(responses_client)
    routine_planner = RoutinePlannerExecutor(responses_client)
    timeline_optimizer = TimelineOptimizerExecutor(responses_client)
    routine_finalizer = RoutineFinalizerExecutor()
    
    # Build the workflow
    builder = WorkflowBuilder()
    builder.set_start_executor(weather_analyst)
    builder.add_edge(weather_analyst, schedule_analyzer)
    builder.add_edge(schedule_analyzer, routine_planner)
    builder.add_edge(routine_planner, timeline_optimizer)
    builder.add_edge(timeline_optimizer, routine_finalizer)
    
    workflow = builder.build()
    
    print("Morning Routine AI Agent Workflow created successfully")
    return workflow

async def demo_morning_routine_scenario():
    """
    Demonstrates the AI agent workflow with a realistic morning scenario
    """
    print("=" * 70)
    print("DAILY LIFE SCENARIO: AI-Powered Morning Routine")
    print("=" * 70)
    print()
    print("Scenario: Sarah is a software developer who wants to optimize")
    print("her morning routine using AI agents. She works remotely but has")
    print("early meetings and wants to include exercise and healthy habits.")
    print()
    
    # Create the workflow
    workflow = await create_morning_routine_workflow()
    
    # Create a realistic person profile
    sarah_profile = PersonProfile(
        name="Sarah Chen",
        work_start_time="8:30 AM",
        preferences=["exercise", "healthy breakfast", "meditation", "coffee", "news"],
        location="Seattle, WA",
        fitness_level="intermediate",
        metadata={
            "job_role": "software_developer",
            "work_type": "remote_with_early_meetings",
            "dietary_preferences": ["vegetarian", "protein_focused"],
            "exercise_preferences": ["yoga", "running", "strength_training"]
        }
    )
    
    print(f"Profile: {sarah_profile.name}")
    print(f"Location: {sarah_profile.location}")
    print(f"Work starts: {sarah_profile.work_start_time}")
    print(f"Fitness level: {sarah_profile.fitness_level}")
    print(f"Preferences: {', '.join(sarah_profile.preferences)}")
    print()
    
    # Run the workflow with real-time AI agent monitoring
    print("Starting AI agent morning routine workflow...")
    print("-" * 50)
    
    try:
            async for event in workflow.run_stream(sarah_profile):
                # Handle different event types
                if isinstance(event, WorkflowOutputEvent):
                    print("-" * 50)
                    print("AI MORNING ROUTINE COMPLETE")
                    print("-" * 50)
                    result = event.data
                    
                    if result["status"] == "completed":
                        print(f"Personalized routine created for {result['person_name']}")
                        print(f"Location: {result['location']}")
                        print(f"Work starts: {result['work_start_time']}")
                        print()
                        
                        # Show weather insights
                        print("Weather Insights:")
                        print(f"   {result['weather_insights']}")
                        print()
                        
                        # Show schedule insights
                        print("Schedule Insights:")
                        print(f"   {result['schedule_insights']}")
                        print()
                        
                        # Show routine steps
                        print("Morning Routine Steps:")
                        for i, step in enumerate(result['routine_steps'][:8], 1):  # Show first 8 steps
                            step_clean = step.replace('•', '').replace('-', '').strip()
                            if step_clean:
                                print(f"   {i}. {step_clean}")
                        if len(result['routine_steps']) > 8:
                            print(f"   ... and {len(result['routine_steps']) - 8} more steps")
                        print()
                        
                        # Show final timeline
                        print("Optimized Timeline:")
                        timeline_lines = result['final_timeline'].split('\n')[:6]  # Show first 6 lines
                        for line in timeline_lines:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                print(f"   {line}")
                        print()
                        
                        # Show component summary
                        components = result['total_components']
                        print("Workflow Components:")
                        print(f"   Weather Analysis: {components['weather_analysis']}")
                        print(f"   Schedule Analysis: {components['schedule_analysis']}")
                        print(f"   Routine Steps: {components['routine_steps']} steps")
                        print(f"   Timeline Optimized: {components['timeline_optimized']}")
                        
                    else:
                        print(f"Routine creation failed: {result['reason']}")
                    
                    return result
                else:
                    # Print basic event info for other event types
                    print(f"Workflow event: {type(event).__name__}")
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure Azure CLI is authenticated: az login")
        print("2. Check Azure OpenAI service access")
        print("3. Verify environment variables if using custom config")
        return None

async def show_workflow_architecture():
    """
    Shows the AI agent workflow structure
    """
    print("\n" + "=" * 70)
    print("AI AGENT WORKFLOW ARCHITECTURE")
    print("=" * 70)
    print()
    print("Morning Routine AI Agent Pipeline:")
    print()
    print("  Person Profile")
    print("      ↓")
    print("  [Weather Analyst] - AI Agent: Weather analysis & clothing advice")
    print("      ↓")
    print("  [Schedule Analyzer] - AI Agent: Work schedule & time optimization")
    print("      ↓")
    print("  [Routine Planner] - AI Agent: Detailed activity planning")
    print("      ↓")
    print("  [Timeline Optimizer] - AI Agent: Efficiency & parallel activities")
    print("      ↓")
    print("  [Routine Finalizer] - System: Package & validate final routine")
    print("      ↓")
    print("  Personalized Morning Routine")
    print()
    print("Each AI agent specializes in:")
    print("   - Weather Analyst: Conditions, clothing, outdoor/indoor activities")
    print("   - Schedule Analyzer: Work timing, priorities, buffer time")
    print("   - Routine Planner: Step-by-step activities with preferences")
    print("   - Timeline Optimizer: Parallel tasks, efficiency, alternatives")
    print("   - Routine Finalizer: Validation, formatting, delivery")
    print()
    print("Technical Features:")
    print("   - Real Azure AI agents with specialized instructions")
    print("   - Sequential processing with data enrichment")
    print("   - Error handling and graceful degradation")
    print("   - Streaming updates and real-time monitoring")
    print("   - Proper async context management")

async def main():
    """
    Main demo function
    """
    print("Microsoft Agent Framework - AI Agents Workflow Demo")
    print("Real AI Agents for Daily Life Scenarios")
    print()
    
    # Show the architecture first
    await show_workflow_architecture()
    
    # Run the demo
    result = await demo_morning_routine_scenario()
    
    print("\n" + "=" * 70)
    print("LEARNING OUTCOMES FOR EARLY CAREER DEVELOPERS")
    print("=" * 70)
    print()
    print("You learned about:")
    print("  - Creating specialized AI agents with specific instructions")
    print("  - Building sequential workflows with Microsoft Agent Framework")
    print("  - Proper Azure AI client setup and authentication")
    print("  - Error handling and graceful failure management")
    print("  - Real-time workflow monitoring and streaming")
    print("  - Data transformation through multiple AI agent stages")
    print()
    print("Advanced concepts demonstrated:")
    print("  - Async context management with Azure resources")
    print("  - Agent factory patterns for resource efficiency")
    print("  - Dataclass usage for structured data flow")
    print("  - Event-driven architecture with workflow events")
    print("  - Professional error handling and debugging")
    print()
    print("Next steps to explore:")
    print("  - Add conditional branching based on preferences")
    print("  - Implement parallel agent processing for efficiency")
    print("  - Add persistent storage for routine history")
    print("  - Create feedback loops for routine improvement")
    print("  - Integrate with real calendar and weather APIs")

if __name__ == "__main__":
    asyncio.run(main())