from prune_serpapi_response import prune_serpapi_response
from agents import function_tool
from dotenv import load_dotenv
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
    """
    print(f"Web searching for: {query}")
    try:
        serp_api_key = os.getenv('SERP_API_KEY')
        if not serp_api_key:
            raise ValueError("SERP_API_KEY environment variable not set for web_search tool.")

        url = f'https://serpapi.com/search?q={query}&api_key={serp_api_key}'
        response = requests.get(url)
        data = response.json()
        print(data)
        return prune_serpapi_response(data)
    except requests.exceptions.RequestException as e:
        print(f"Web search failed: {e}")
        return {"error": f"Could not perform web search: {e}"}
    except Exception as e:
        print(f"An error occurred during web search: {e}")
        return {"error": "An error occurred during web search."}
    


if __name__ == "__main__":
    class Singleton:
        _instance = None

        def __new__(cls, *args, **kwargs):
            print('>>>> ')
            if not cls._instance:   # if no instance exists, create one
                cls._instance = super().__new__(cls)
            return cls._instance

    a = Singleton()
    b = Singleton()
    print(a is b)  # True -> same instance
