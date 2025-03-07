import json
import os
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv
from exa_py import Exa
from langfuse.openai import OpenAI
from openai import OpenAI

#--------------------------------
# Environment Setup
#--------------------------------
load_dotenv()

# Initialize API clients
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
exa = Exa(api_key=os.getenv("EXA_API_KEY"))

#--------------------------------
# Configuration
#--------------------------------
SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are a sports research assistant. Provide accurate and up-to-date sports information using the search tool."
}

# Define the search tool that GPT can use
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "exa_search",
            "description": "Search for sports information including schedules, scores, stats, and news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The sports-related search query to perform.",
                    },
                },
                "required": ["query"],
            },
        },
    }
]

#--------------------------------
# Core Functions
#--------------------------------
def get_time_context():
    """Get current time context in EST"""
    est = pytz.timezone('US/Eastern')
    current_time = datetime.now(est)
    return f"Current time context - Date: {current_time.strftime('%A, %B %d, %Y')}, Time: {current_time.strftime('%I:%M %p')} EST\n\n"

def exa_search(query: str):
    """Execute web search using Exa API"""
    return exa.search_and_contents(
        query=query,
        type='auto',
        num_results=9,
        text = True
    )

def process_tool_calls(tool_calls, messages):
    """Process GPT's tool calls and execute searches"""
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        if function_name == "exa_search":
            search_results = exa_search(**function_args)
            messages.append({
                "role": "tool",
                "content": str(search_results),
                "tool_call_id": tool_call.id,
            })
    
    return messages

def process_query(query: str):
    """Main query processing pipeline"""
    # Step 1: Initialize conversation with system message
    messages = [SYSTEM_MESSAGE]
    
    # Step 2: Add time context and user query
    time_context = get_time_context()
    messages.append({"role": "user", "content": f"{time_context}{query}"})
    
    try:
        # Step 3: Ask GPT to analyze query and decide on search strategy
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        
        message = completion.choices[0].message
        tool_calls = message.tool_calls
        
        if tool_calls:
            # Step 4: If GPT wants to search, process the search requests
            messages.append(message)
            messages = process_tool_calls(tool_calls, messages)
            
            # Step 5: Ask GPT to analyze search results and answer the query
            messages.append({
                "role": "user",
                "content": "Answer my previous query based on the search results. Response must be in markdown format."
            })
            
            # Step 6: Get final response from GPT
            final_completion = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
            )
            return final_completion.choices[0].message.content
        
        # If no search needed, return direct GPT response
        return message.content
            
    except Exception as e:
        return f"Error: {str(e)}"

#--------------------------------
# Test Runner
#--------------------------------
if __name__ == "__main__":
    # Simple test query
    test_query = "What NBA games are scheduled for tonight?"
    if len(sys.argv) > 1:
        test_query = " ".join(sys.argv[1:])
    
    print(f"\nQuery: {test_query}")
    print("\nProcessing...")
    response = process_query(test_query)
    print(f"\nResponse: {response}\n")