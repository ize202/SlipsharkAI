import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_perplexity_chat(stream=False):
    """
    Test the Perplexity AI chat completions endpoint
    Args:
        stream (bool): Whether to use streaming mode
    """
    try:
        # Initialize client with Perplexity base URL
        client = OpenAI(
            api_key=os.getenv('PERPLEXITY_API_KEY'),
            base_url="https://api.perplexity.ai"
        )

        # Test messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant. Be precise and concise."
            },
            {
                "role": "user",
                "content": "Nba games today"
            }
        ]

        if stream:
            print("\nTesting streaming response:")
            response_stream = client.chat.completions.create(
                model="sonar",
                messages=messages,
                stream=True
            )
            for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    print(chunk.choices[0].delta.content, end='')
            print("\n")
        else:
            print("\nTesting regular response:")
            response = client.chat.completions.create(
                model="sonar",
                messages=messages
            )
            print(response.choices[0].message.content)

    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    # Test both streaming and non-streaming
    test_perplexity_chat(stream=False)
    test_perplexity_chat(stream=True) 