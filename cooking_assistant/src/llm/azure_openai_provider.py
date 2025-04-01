import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import argparse
from typing import List, Type, Union
from pydantic import BaseModel, ConfigDict
import json

class Recipe(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    recipe_name: str
    ingredients: List[str]
    instructions: List[str]

SYSTEM_PROMPT_RECIPE = (
    "You are a helpful assistant that provides recipes in JSON format matching the Recipe schema. "
    "The JSON object must have keys: 'recipe_name' (string), 'ingredients' (list of strings), "
    "'instructions' (list of strings). "
    "If a step involves a specific duration (e.g., 'boil for 10 minutes'), "
    "you MUST include a timer marker in the instruction string for that step. "
    "Use the exact format [TIMER: <duration_in_seconds> <unique_timer_id>]. "
    "Replace <duration_in_seconds> with the total seconds and <unique_timer_id> "
    "with a short, descriptive ID (use underscores, e.g., 'pasta_boiling')."
)

SYSTEM_PROMPT_GENERAL = (
    "You are a helpful cooking assistant. Your goal is to guide the user through their cooking process. "
    "Refer to the provided message history, including the current recipe state if available. "
    "If you mention a specific duration for a cooking step (e.g., 'boil for 10 minutes', 'let rest for 5 minutes'), "
    "you MUST also include a timer marker in your response. "
    "Use the exact format [TIMER: <duration_in_seconds> <unique_timer_id>]. "
    "Replace <duration_in_seconds> with the total number of seconds, and <unique_timer_id> "
    "with a short, descriptive ID for the timer (use underscores instead of spaces, e.g., 'pasta_boiling'). "
    "Only include this timer marker if a specific duration is mentioned for an action. "
    "Additionally, based on the conversation history and the user's last message, determine if the user is implicitly or explicitly moving to the next step of the recipe/process. "
    "If you conclude they are moving to a new step, you MUST include a step marker in your response. "
    "Use the exact format [STEP: <step_index>]. "
    "Replace <step_index> with the zero-based index of the new step the user is now on. "
    "For example, if the user was on step 0 and asks 'what's next?', your response might guide them on step 1 and include '[STEP: 1]'. "
    "Only include the [STEP: <step_index>] marker if you determine the user is transitioning to a new step. Do not include it otherwise." 
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
        # Initialize the client once
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint
        )

    # Updated signature: response_format expects a Type[BaseModel], return type is Union[str, BaseModel]
    def send_prompt(self, prompt: str, response_format: Type[BaseModel] = None, max_tokens: int = 400) -> Union[str, BaseModel]:
        """
        Sends a prompt to the specified deployment and returns the generated response.

        :param prompt: The input prompt to send to the model.
        :param response_format: Optional Pydantic model class (e.g., Recipe) to parse the response into.
        :param max_tokens: The maximum number of tokens to generate in the response.
        :return: The generated response from the model (string or Pydantic object).
        """
        try:
            # Check if the requested format is our Recipe model
            if response_format == Recipe:
                # Use response_model for structured JSON output matching the Pydantic model
                response = self.client.beta.chat.completions.parse(
                    model=self.deployment_name, # Use instance variable for deployment name
                    messages=[
                        # SYSTEM_PROMPT_RECIPE is mainly for the structure, not conversational step tracking
                        {"role": "system", "content": SYSTEM_PROMPT_RECIPE},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=Recipe, # Pass the class itself
                    temperature=0.7,
                    max_tokens=max_tokens # Allow more tokens for potential recipes
                )
                # When using response_model with recent openai versions, the parsed object
                # is often directly available or within response.choices[0].message.tool_calls or similar.
                # However, the most reliable way specified by Azure docs sometimes is still
                # getting the content and parsing. Let's assume content holds the JSON string.
                
                # Adjusting based on potential new API behavior for 'parse'
                # The .parse() method might directly return the Pydantic object.
                if isinstance(response, Recipe):
                    return response
                elif hasattr(response, 'choices') and response.choices: # Check if it's the older structure
                    recipe_json_string = response.choices[0].message.content
                    if recipe_json_string:
                        parsed_recipe = Recipe.model_validate_json(recipe_json_string)
                        return parsed_recipe
                    else:
                        raise ValueError("LLM response content is empty or not in expected format for Recipe.")
                else:
                    # Handle unexpected response structure from .parse()
                    raise ValueError(f"Unexpected response structure from LLM parse method: {type(response)}")

            else:
                # Handle general prompts returning strings
                response = self.client.chat.completions.create(
                    model=self.deployment_name, # Use instance variable
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_GENERAL},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=max_tokens
                )
                res = response.choices[0].message.content
                return res # Return string for general prompts

        except Exception as e:
            # Log the error for debugging purposes
            print(f"An error occurred during LLM call: {str(e)}")
            # Return an error message string or re-raise depending on desired error handling
            return f"An error occurred: {str(e)}"

# Create and export the provider instance
load_dotenv()
api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01") # Get version, provide default

if not api_key or not endpoint or not deployment_name:
    raise ValueError("Please set the AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME environment variables.")

# Pass the required arguments including api_version
openai_provider = AzureOpenAIProvider(api_key, endpoint, deployment_name, api_version)

# Example usage (keep commented out):
# if __name__ == "__main__":
#     load_dotenv()
#     api_key = os.getenv("AZURE_OPENAI_API_KEY")
#     endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
#     deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
#     api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    
#     parser = argparse.ArgumentParser(description='Interactive Cooking Assistant')
#     parser.add_argument('--prompt', type=str, required=True, help='Direct prompt to send to the assistant')
#     args = parser.parse_args()

#     if not api_key or not endpoint or not deployment_name:
#         raise ValueError("Please set the AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME environment variables.")

#     provider = AzureOpenAIProvider(api_key, endpoint, deployment_name, api_version)
    
#     # Example for getting a recipe
#     # Assumes the prompt asks for a recipe, e.g., "Give me a recipe for scrambled eggs"
#     print("--- Testing Recipe Request ---")
#     recipe_response = provider.send_prompt(args.prompt, response_format=Recipe)
#     if isinstance(recipe_response, Recipe):
#         print("Successfully parsed Recipe:")
#         print(f"  Name: {recipe_response.recipe_name}")
#         print(f"  Ingredients: {recipe_response.ingredients}")
#         print(f"  Instructions: {recipe_response.instructions}")
#     elif isinstance(recipe_response, str):
#         print(f"Received string (likely an error): {recipe_response}")
#     else:
#         print("Received unexpected response type.")

#     # Example for a general question
#     print("\n--- Testing General Request ---")
#     general_prompt = "How long should I cook chicken breast?"
#     general_response = provider.send_prompt(general_prompt)
#     print(f"Prompt: {general_prompt}")
#     print(f"Response: {general_response}")
