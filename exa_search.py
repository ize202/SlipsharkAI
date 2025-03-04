import json
import os
import sys
from typing import Dict, Any

from dotenv import load_dotenv
from exa_py import Exa
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize clients
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
exa = Exa(api_key=os.getenv("EXA_API_KEY"))

SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are a sports research assistant. Provide accurate and up-to-date sports information using the search tool."
}

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

def exa_search(query: str) -> Dict[str, Any]:
    """Perform a web search using Exa"""
    return exa.search_and_contents(
        query=query,
        type='auto',
        highlights=True,
        num_results=5
    )

def process_query(query: str) -> str:
    """Process a single query and return the response"""
    messages = [SYSTEM_MESSAGE]
    messages.append({"role": "user", "content": query})
    
    try:
        # First completion to get search parameters
        completion = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        
        message = completion.choices[0].message
        tool_calls = message.tool_calls
        
        if tool_calls:
            messages.append(message)
            
            # Process search
            for tool_call in tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                search_results = exa_search(**function_args)
                messages.append({
                    "role": "tool",
                    "content": str(search_results),
                    "tool_call_id": tool_call.id,
                })
            
            # Add the prompt to process search results
            messages.append({
                "role": "user",
                "content": "Answer my previous query based on the search results."
            })
            
            # Get final answer
            final_completion = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
            )
            return final_completion.choices[0].message.content
        
        return message.content
            
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Simple test query
    test_query = "What NBA games are scheduled for tonight?"
    if len(sys.argv) > 1:
        test_query = " ".join(sys.argv[1:])
    
    print(f"\nQuery: {test_query}")
    print("\nProcessing...")
    response = process_query(test_query)
    print(f"\nResponse: {response}\n")