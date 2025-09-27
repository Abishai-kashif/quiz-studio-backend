from agents import function_tool
from dotenv import load_dotenv
from prune_serpapi_reponse import prune_serpapi_response
import requests
import os

load_dotenv()

@function_tool
def web_search(query: str) -> dict[str, any]:
    """
    Performs a real-time web search to gather information from the internet.
    This tool is ideal for getting information from urls.

    Args:
        query (str): The search query to be performed. Be specific and concise.
                     Examples: "https://github.com/openai/openai-agents-python",

    Returns:
        dict: A dictionary containing search results.

    Error & Fallback Behavior:
    - If the provided URL cannot be accessed (e.g., private, expired, or 
        personal content like chat links), return a clear error message 
        indicating that the source is not accessible.
    - If the query returns no results, return a message stating 
        "No results found for the given query."
    - Always provide explicit feedback rather than silent failure, 
        so the user knows whether the issue is with the link, permissions, 
        or the query itself.
    """
    print(f"Web searching for: {query}")
    try:
        serp_api_key = os.getenv('SERP_API_KEY')
        if not serp_api_key:
            raise ValueError("SERP_API_KEY environment variable not set for web_search tool.")

        url = f'https://serpapi.com/search?q={query}&api_key={serp_api_key}'
        response = requests.get(url)
        data = response.json()
        return prune_serpapi_response(data)
    except requests.exceptions.RequestException as e:
        print(f"Web search failed: {e}")
        return {"error": f"Could not perform web search: {e}"}
    except Exception as e:
        print(f"An error occurred during web search: {e}")
        return {"error": "An error occurred during web search."}