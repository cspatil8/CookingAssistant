import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import argparse
from typing import List
from pydantic import BaseModel, ConfigDict

class Recipe(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    recipe_name: str
    ingredients: List[str]
    instructions: List[str]

SYSTEM_PROMPT_RECIPE = (
    "You are a helpful assistant that provides recipes in JSON format. "
    "If a step involves a specific duration (e.g., 'boil for 10 minutes'), "
    "you MUST include a timer marker in the instruction string for that step. "
    "Use the exact format [TIMER: <duration_in_seconds> <unique_timer_id>]. "
    "Replace <duration_in_seconds> with the total seconds and <unique_timer_id> "
    "with a short, descriptive ID (use underscores, e.g., 'pasta_boiling')."
)

SYSTEM_PROMPT_GENERAL = (
    "You are a helpful cooking assistant. "
    "If you mention a specific duration for a cooking step (e.g., 'boil for 10 minutes', 'let rest for 5 minutes'), "
    "you MUST also include a timer marker in your response. "
    "Use the exact format [TIMER: <duration_in_seconds> <unique_timer_id>]. "
    "Replace <duration_in_seconds> with the total number of seconds, and <unique_timer_id> "
    "with a short, descriptive ID for the timer (use underscores instead of spaces, e.g., 'pasta_boiling'). "
    "Only include this marker if a specific duration is mentioned for an action."
)

class AzureOpenAIProvider:
    def __init__(self, api_key: str, endpoint: str, deployment_name: str, api_version: str = "2024-02-01"):
        """
        Initializes the AzureOpenAIProvider with the necessary credentials and deployment details.

        :param api_key: Your Azure OpenAI API key.
        :param endpoint: The endpoint URL of your Azure OpenAI resource.
        :param deployment_name: The name of your model deployment.
        :param api_version: The API version to use (default is "2024-02-01").
        """
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment_name = deployment_name
        self.api_version = api_version

    def send_prompt(self, prompt: str, response_format: BaseModel = None, max_tokens: int = 100) -> str:
        """
        Sends a prompt to the specified deployment and returns the generated response.

        :param prompt: The input prompt to send to the model.
        :param max_tokens: The maximum number of tokens to generate in the response.
        :param response_format: Optional Pydantic model to parse the response into.
        :return: The generated response from the model.
        """

        try:
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
        
            if response_format == "recipe":
                response = client.beta.chat.completions.parse(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_RECIPE},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=Recipe,
                    temperature=0.7
                )
                res = response.choices[0].message.content
            else:
                response = client.chat.completions.create(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_GENERAL},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=max_tokens
                )
                res = response.choices[0].message.content

            return res
        except Exception as e:
            return f"An error occurred: {str(e)}"

# Create and export the provider instance
load_dotenv()
api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

if not api_key or not endpoint or not deployment_name:
    raise ValueError("Please set the AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME environment variables.")

openai_provider = AzureOpenAIProvider(api_key, endpoint, deployment_name)

# Example usage:
# if __name__ == "__main__":
#     load_dotenv()
#     # Retrieve your API key and endpoint from environment variables for security
#     api_key = os.getenv("AZURE_OPENAI_API_KEY")
#     endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
#     deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")  # Replace with your actual deployment name
    
#     parser = argparse.ArgumentParser(description='Interactive Cooking Assistant')
#     # parser.add_argument('--simulate', action='store_true', help='Simulate timers (for testing)')
#     # parser.add_argument('--recipe', type=str, help='Path to recipe file (optional)')
#     parser.add_argument('--prompt', type=str, help='Direct prompt to send to the assistant')
#     args = parser.parse_args()

#     if not api_key or not endpoint:
#         raise ValueError("Please set the AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables.")

#     provider = AzureOpenAIProvider(api_key, endpoint, deployment_name)
#     prompt = args.prompt
#     response = provider.send_prompt(prompt)
