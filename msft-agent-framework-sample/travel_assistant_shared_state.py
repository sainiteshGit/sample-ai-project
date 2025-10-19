"""
Travel Assistant with Shared State - Microsoft Agent Framework Example
=====================================================================

This example demonstrates how to use shared state in workflows to allow different
executors to collaborate by reading and writing to a common memory space.

Scenario: Building a travel assistant that collects destination and dates from a user,
then recommends flights and hotels using the shared state data.

Why Shared State Matters:
- Multiple nodes need access to the same data
- Inputs arrive at different times (destination now, dates later)
- Avoid passing bulky data through every message
- Keep messages lightweight and workflows maintainable
"""

import os
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
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
class UserInput:
    """Represents user input at each step"""
    step: int
    content: str
    input_type: str  # "destination", "dates", "preferences"


@dataclass
class TravelPlan:
    """Shared state that flows through the workflow"""
    destination: Optional[str] = None
    travel_dates: Optional[Dict[str, str]] = None  # {"start": "2025-12-20", "end": "2025-12-30"}
    preferences: Optional[Dict[str, str]] = None  # {"budget": "mid-range", "style": "adventure"}
    flight_recommendations: Optional[str] = None
    hotel_recommendations: Optional[str] = None
    itinerary: Optional[str] = None
    status: str = "initialized"
    metadata: Dict[str, Any] = field(default_factory=dict)


class DestinationCollectorExecutor(Executor):
    """
    First stage: Collect destination from user
    
    This executor captures the destination and stores it in shared state.
    Other executors can access this information later without re-asking the user.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="destination_collector")
    
    @handler
    async def collect_destination(
        self,
        user_input: UserInput,
        ctx: WorkflowContext[TravelPlan]
    ) -> None:
        print(f"Collecting destination from user input: {user_input.content}")
        
        try:
            # Extract destination from user input using AI
            agent = self.responses_client.create_agent(
                name="DestinationAnalyzer",
                instructions="You are a travel assistant. Extract the destination city/country from user input. Return only the destination name, nothing else."
            )
            
            response = await agent.run(user_input.content)
            destination = response.text.strip()
            
            # Get or create shared state
            travel_plan = TravelPlan(
                destination=destination,
                status="destination_collected",
                metadata={"step": user_input.step, "input_type": user_input.input_type}
            )
            
            print("Destination collected: " + destination)
            print("Storing in shared state")
            
            # Write to shared state via context
            await ctx.set_shared_state("travel_plan", travel_plan)
            # Send forward to next executor
            await ctx.send_message(travel_plan)
            
        except Exception as e:
            print(f"Destination collection failed: {e}")
            error_plan = TravelPlan(
                status="destination_error",
                metadata={"error": str(e)}
            )
            await ctx.send_message(error_plan)


class DateCollectorExecutor(Executor):
    """
    Second stage: Collect travel dates from user
    
    This executor reads the destination from shared state (set by previous executor)
    and adds travel dates to the shared state. No need to pass destination in messages.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="date_collector")
    
    @handler
    async def collect_dates(
        self,
        plan: TravelPlan,
        ctx: WorkflowContext[TravelPlan]
    ) -> None:
        print(f"Collecting travel dates based on previous stage...")
        
        # For demonstration, use a simulated user input
        user_input = "I want to travel from December 20, 2025 to December 30, 2025"
        print(f"Simulated User Input: {user_input}")
        
        try:
            # Read from shared state (destination set by previous executor)
            shared_state = await ctx.get_shared_state("travel_plan")
            
            if shared_state and shared_state.destination:
                print(f"Reading from shared state - Destination: {shared_state.destination}")
            
            # Extract dates from user input using AI
            agent = self.responses_client.create_agent(
                name="DateAnalyzer",
                instructions="You are a travel assistant. Extract start and end dates from user input. Return in format: START_DATE: YYYY-MM-DD, END_DATE: YYYY-MM-DD"
            )
            
            response = await agent.run(user_input)
            dates_text = response.text.strip()
            
            # Parse dates
            dates_dict = {}
            if "START_DATE:" in dates_text and "END_DATE:" in dates_text:
                parts = dates_text.split("START_DATE:")[1].split("END_DATE:")
                dates_dict["start"] = parts[0].strip()
                dates_dict["end"] = parts[1].strip()
            
            # Update shared state
            base_metadata = shared_state.metadata if shared_state else {}
            updated_plan = TravelPlan(
                destination=shared_state.destination if shared_state else None,
                travel_dates=dates_dict,
                status="dates_collected",
                metadata={**base_metadata, "dates_added": True}
            )
            
            print(f"Travel dates collected: {dates_dict}")
            print("Updating shared state with dates")
            
            await ctx.set_shared_state("travel_plan", updated_plan)
            await ctx.send_message(updated_plan)
            
        except Exception as e:
            print(f"Date collection failed: {e}")
            shared_state = await ctx.get_shared_state("travel_plan")
            error_plan = TravelPlan(
                destination=shared_state.destination if shared_state else None,
                status="date_error",
                metadata={"error": str(e)}
            )
            await ctx.send_message(error_plan)


class PreferenceCollectorExecutor(Executor):
    """
    Third stage: Collect travel preferences from user
    
    This executor reads both destination and dates from shared state,
    then adds user preferences. The shared state now contains all three pieces of info.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="preference_collector")
    
    @handler
    async def collect_preferences(
        self,
        plan: TravelPlan,
        ctx: WorkflowContext[TravelPlan]
    ) -> None:
        print(f"Collecting travel preferences based on previous stage...")
        
        # For demonstration, use a simulated user input
        user_input = "I prefer budget-friendly adventure travel with unique experiences"
        print(f"Simulated User Input: {user_input}")
        
        try:
            # Read full shared state from previous executors
            shared_state = await ctx.get_shared_state("travel_plan")
            
            if shared_state:
                print(f"Reading from shared state:")
                print(f"  - Destination: {shared_state.destination}")
                print(f"  - Travel Dates: {shared_state.travel_dates}")
            
            # Extract preferences using AI
            agent = self.responses_client.create_agent(
                name="PreferenceAnalyzer",
                instructions="You are a travel assistant. Extract travel preferences (budget level, travel style, accommodation type) from user input. Return as KEY: VALUE pairs."
            )
            
            response = await agent.run(user_input)
            preferences_text = response.text.strip()
            
            # Parse preferences
            preferences_dict = {}
            for line in preferences_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    preferences_dict[key.strip().lower()] = value.strip()
            
            # Update shared state with all information
            base_metadata = shared_state.metadata if shared_state else {}
            updated_plan = TravelPlan(
                destination=shared_state.destination if shared_state else None,
                travel_dates=shared_state.travel_dates if shared_state else None,
                preferences=preferences_dict,
                status="preferences_collected",
                metadata={**base_metadata, "preferences_added": True}
            )
            
            print(f"Travel preferences collected: {preferences_dict}")
            print("Shared state now complete with all user information")
            
            await ctx.set_shared_state("travel_plan", updated_plan)
            await ctx.send_message(updated_plan)
            
        except Exception as e:
            print(f"Preference collection failed: {e}")
            shared_state = await ctx.get_shared_state("travel_plan")
            error_plan = TravelPlan(
                destination=shared_state.destination if shared_state else None,
                travel_dates=shared_state.travel_dates if shared_state else None,
                status="preference_error",
                metadata={"error": str(e)}
            )
            await ctx.send_message(error_plan)


class FlightRecommenderExecutor(Executor):
    """
    Fourth stage: Recommend flights
    
    This executor can now access all information from shared state:
    destination, travel dates, and preferences. It generates flight recommendations
    without any of this information being passed through messages.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="flight_recommender")
    
    @handler
    async def recommend_flights(
        self,
        plan: TravelPlan,
        ctx: WorkflowContext[TravelPlan]
    ) -> None:
        print("Recommending flights based on shared state data...")
        
        try:
            # Read complete shared state
            shared_state = await ctx.get_shared_state("travel_plan")
            
            if not shared_state or shared_state.status not in ["preferences_collected"]:
                print("Skipping flight recommendation - incomplete travel information")
                await ctx.send_message(plan)
                return
            
            # Check if all required information is available
            if not all([shared_state.destination, shared_state.travel_dates, shared_state.preferences]):
                print("Missing required information for flight recommendations")
                await ctx.send_message(plan)
                return
            
            # Use AI to recommend flights
            agent = self.responses_client.create_agent(
                name="FlightRecommender",
                instructions="You are an expert travel advisor. Provide specific, practical flight recommendations based on destination, dates, and travel preferences. Include airline suggestions, price ranges, and booking tips."
            )
            
            prompt = f"""
            Based on the following travel information, recommend flights:
            
            Destination: {shared_state.destination}
            Travel Dates: {shared_state.travel_dates['start']} to {shared_state.travel_dates['end']}
            Travel Preferences:
            {chr(10).join([f"  - {k}: {v}" for k, v in shared_state.preferences.items()])}
            
            Provide 2-3 flight recommendations with:
            1. Recommended airlines
            2. Estimated price ranges
            3. Booking tips specific to this destination
            4. Best time to book
            """
            
            response = await agent.run(prompt)
            flight_recommendations = response.text
            
            # Update shared state with flight recommendations
            base_metadata = shared_state.metadata if shared_state else {}
            updated_plan = TravelPlan(
                destination=shared_state.destination,
                travel_dates=shared_state.travel_dates,
                preferences=shared_state.preferences,
                flight_recommendations=flight_recommendations,
                status="flights_recommended",
                metadata={**base_metadata, "flights_added": True}
            )
            
            print("Flight recommendations added to shared state")
            await ctx.set_shared_state("travel_plan", updated_plan)
            await ctx.send_message(updated_plan)
            
        except Exception as e:
            print(f"Flight recommendation failed: {e}")
            shared_state = await ctx.get_shared_state("travel_plan")
            error_plan = TravelPlan(
                destination=shared_state.destination if shared_state else None,
                travel_dates=shared_state.travel_dates if shared_state else None,
                preferences=shared_state.preferences if shared_state else None,
                status="flight_error",
                metadata={"error": str(e)}
            )
            await ctx.send_message(error_plan)


class HotelRecommenderExecutor(Executor):
    """
    Fifth stage: Recommend hotels
    
    This executor demonstrates the scalability of shared state. We can add
    this new executor without modifying any existing ones. It simply reads
    from shared state and adds its recommendations.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="hotel_recommender")
    
    @handler
    async def recommend_hotels(
        self,
        plan: TravelPlan,
        ctx: WorkflowContext[TravelPlan]
    ) -> None:
        print("Recommending hotels based on shared state data...")
        
        try:
            # Read complete shared state
            shared_state = await ctx.get_shared_state("travel_plan")
            
            if not shared_state or not all([
                shared_state.destination,
                shared_state.travel_dates,
                shared_state.preferences,
                shared_state.flight_recommendations
            ]):
                print("Skipping hotel recommendation - incomplete travel information")
                await ctx.send_message(plan)
                return
            
            # Use AI to recommend hotels
            agent = self.responses_client.create_agent(
                name="HotelRecommender",
                instructions="You are an expert travel advisor. Provide specific, practical hotel recommendations based on destination, dates, and travel preferences. Include specific hotel names, price ranges, and location tips."
            )
            
            prompt = f"""
            Based on the following travel information, recommend hotels:
            
            Destination: {shared_state.destination}
            Travel Dates: {shared_state.travel_dates['start']} to {shared_state.travel_dates['end']}
            Travel Preferences:
            {chr(10).join([f"  - {k}: {v}" for k, v in shared_state.preferences.items()])}
            
            Provide 2-3 hotel recommendations with:
            1. Specific hotel names and locations
            2. Estimated price ranges (per night)
            3. Why each hotel suits the travel preferences
            4. Booking platforms and tips
            5. Proximity to attractions
            """
            
            response = await agent.run(prompt)
            hotel_recommendations = response.text
            
            # Update shared state with hotel recommendations
            base_metadata = shared_state.metadata if shared_state else {}
            updated_plan = TravelPlan(
                destination=shared_state.destination,
                travel_dates=shared_state.travel_dates,
                preferences=shared_state.preferences,
                flight_recommendations=shared_state.flight_recommendations,
                hotel_recommendations=hotel_recommendations,
                status="hotels_recommended",
                metadata={**base_metadata, "hotels_added": True}
            )
            
            print("Hotel recommendations added to shared state")
            await ctx.set_shared_state("travel_plan", updated_plan)
            await ctx.send_message(updated_plan)
            
        except Exception as e:
            print(f"Hotel recommendation failed: {e}")
            shared_state = await ctx.get_shared_state("travel_plan")
            error_plan = TravelPlan(
                destination=shared_state.destination if shared_state else None,
                travel_dates=shared_state.travel_dates if shared_state else None,
                preferences=shared_state.preferences if shared_state else None,
                flight_recommendations=shared_state.flight_recommendations if shared_state else None,
                status="hotel_error",
                metadata={"error": str(e)}
            )
            await ctx.send_message(error_plan)


class ItineraryBuilderExecutor(Executor):
    """
    Final stage: Build complete itinerary
    
    This executor has access to all shared state data: destination, dates,
    preferences, flight and hotel recommendations. It synthesizes all this
    information into a cohesive travel itinerary.
    """
    
    def __init__(self, responses_client: AzureOpenAIResponsesClient):
        self.responses_client = responses_client
        super().__init__(id="itinerary_builder")
    
    @handler
    async def build_itinerary(
        self,
        plan: TravelPlan,
        ctx: WorkflowContext[TravelPlan]
    ) -> None:
        print("Building complete travel itinerary...")
        
        try:
            # Read complete shared state
            shared_state = await ctx.get_shared_state("travel_plan")
            
            if not shared_state or shared_state.status != "hotels_recommended":
                print("Cannot build itinerary - missing hotel recommendations")
                error_result = {
                    "status": "failed",
                    "reason": "Incomplete travel plan data",
                    "destination": shared_state.destination if shared_state else None
                }
                await ctx.yield_output(error_result)
                return
            
            # Use AI to build comprehensive itinerary
            agent = self.responses_client.create_agent(
                name="ItineraryBuilder",
                instructions="You are an expert travel itinerary planner. Create a day-by-day itinerary that ties together flights, hotels, and local attractions."
            )
            
            prompt = f"""
            Create a detailed day-by-day travel itinerary for:
            
            Destination: {shared_state.destination}
            Travel Dates: {shared_state.travel_dates['start']} to {shared_state.travel_dates['end']}
            Duration: {len(shared_state.travel_dates) if isinstance(shared_state.travel_dates, dict) else 'unknown'} days
            
            Travel Preferences:
            {chr(10).join([f"  - {k}: {v}" for k, v in shared_state.preferences.items()])}
            
            Recommended Flights Summary:
            {shared_state.flight_recommendations[:200]}...
            
            Recommended Hotels Summary:
            {shared_state.hotel_recommendations[:200]}...
            
            Create a detailed day-by-day itinerary including:
            1. Arrival and hotel check-in
            2. Local attractions and activities
            3. Dining recommendations
            4. Transportation tips
            5. Departure details
            """
            
            response = await agent.run(prompt)
            itinerary = response.text
            
            # Finalize shared state
            final_plan = TravelPlan(
                destination=shared_state.destination,
                travel_dates=shared_state.travel_dates,
                preferences=shared_state.preferences,
                flight_recommendations=shared_state.flight_recommendations,
                hotel_recommendations=shared_state.hotel_recommendations,
                itinerary=itinerary,
                status="complete",
                metadata={**shared_state.metadata, "itinerary_built": True}
            )
            
            print("Travel itinerary completed")
            await ctx.set_shared_state("travel_plan", final_plan)
            
            # Prepare final output
            result = {
                "status": "completed",
                "destination": final_plan.destination,
                "travel_dates": final_plan.travel_dates,
                "preferences": final_plan.preferences,
                "flight_recommendations": final_plan.flight_recommendations[:300] + "..." if final_plan.flight_recommendations else None,
                "hotel_recommendations": final_plan.hotel_recommendations[:300] + "..." if final_plan.hotel_recommendations else None,
                "itinerary": itinerary,
                "complete_travel_plan": final_plan
            }
            
            await ctx.yield_output(result)
            
        except Exception as e:
            print(f"Itinerary building failed: {e}")
            error_result = {
                "status": "failed",
                "error": str(e)
            }
            await ctx.yield_output(error_result)


async def create_travel_assistant_workflow():
    """Creates the complete travel assistant workflow with shared state"""
    print("Setting up Travel Assistant Workflow with Shared State...")
    
    # Initialize Azure OpenAI client
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        raise ValueError("Azure OpenAI environment variables required")
    
    responses_client = AzureOpenAIResponsesClient(
        endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment
    )
    
    # Create executors
    destination_collector = DestinationCollectorExecutor(responses_client)
    date_collector = DateCollectorExecutor(responses_client)
    preference_collector = PreferenceCollectorExecutor(responses_client)
    flight_recommender = FlightRecommenderExecutor(responses_client)
    hotel_recommender = HotelRecommenderExecutor(responses_client)
    itinerary_builder = ItineraryBuilderExecutor(responses_client)
    
    # Build workflow graph
    builder = WorkflowBuilder()
    builder.set_start_executor(destination_collector)
    builder.add_edge(destination_collector, date_collector)
    builder.add_edge(date_collector, preference_collector)
    builder.add_edge(preference_collector, flight_recommender)
    builder.add_edge(flight_recommender, hotel_recommender)
    builder.add_edge(hotel_recommender, itinerary_builder)
    
    workflow = builder.build()
    
    print("Travel Assistant Workflow created successfully")
    return workflow


async def demo_travel_assistant():
    """Demonstrates the travel assistant workflow"""
    print("=" * 70)
    print("TRAVEL ASSISTANT WITH SHARED STATE")
    print("=" * 70)
    print()
    print("This example shows how shared state enables:")
    print("  - Multiple executors to access the same data")
    print("  - Information collection at different times")
    print("  - Clean, lightweight message passing")
    print("  - Easy addition of new executors (hotel recommender)")
    print()
    
    # Create workflow
    workflow = await create_travel_assistant_workflow()
    
    # Simulate user inputs at different steps
    print("Simulating user interactions:")
    print("-" * 70)
    
    # Step 1: User provides destination
    destination_input = UserInput(
        step=1,
        content="I want to go to Paris for a romantic getaway",
        input_type="destination"
    )
    print(f"\nStep 1 - User Input: {destination_input.content}")
    
    try:
        async for event in workflow.run_stream(destination_input):
            if isinstance(event, WorkflowOutputEvent):
                result = event.data
                
                if result.get("status") == "completed":
                    print("-" * 70)
                    print("COMPLETE TRAVEL PLAN GENERATED")
                    print("-" * 70)
                    print(f"\nDestination: {result['destination']}")
                    print(f"Travel Dates: {result['travel_dates']}")
                    print(f"Preferences: {result['preferences']}")
                    
                    print("\nFlight Recommendations:")
                    print(result['flight_recommendations'][:500] + "...")
                    
                    print("\nHotel Recommendations:")
                    print(result['hotel_recommendations'][:500] + "...")
                    
                    print("\nFull Itinerary:")
                    print(result['itinerary'][:500] + "...")
                    
                    return result
                else:
                    print(f"Workflow status: {result.get('status')}")
                    
    except Exception as e:
        print(f"Workflow execution error: {e}")
        return None


async def main():
    """Main entry point"""
    print("Microsoft Agent Framework - Travel Assistant with Shared State")
    print()
    
    # Run demo
    result = await demo_travel_assistant()


if __name__ == "__main__":
    asyncio.run(main())
