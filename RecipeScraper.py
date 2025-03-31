import requests
from bs4 import BeautifulSoup
from openai import AzureOpenAI
import os
from typing import Optional
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

def extract_text_from_url(url: str) -> Optional[str]:
    """
    Extracts text content from a given URL with error handling
    """
    try:
        # Validate URL format
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValueError("Invalid URL format")

        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style']):
            element.decompose()
            
        # Get text content
        text = ' '.join(soup.stripped_strings)
        return text
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def generate_recipe_guide(text: str) -> Optional[str]:
    """
    Uses Azure OpenAI to generate a step-by-step recipe guide
    """
    try:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        prompt = f"""
        Create a clear, step-by-step cooking guide from the following recipe text. 
        If this text doesn't appear to be a recipe, respond with 'This doesn't appear to be a recipe.'
        
        Recipe text:
        {text}
        """

        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "You are a helpful cooking assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating recipe guide: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python RecipeScraper.py <recipe_url>")
        sys.exit(1)

    url = sys.argv[1]
    
    # Extract text from URL
    print("Fetching recipe from URL...")
    text = extract_text_from_url(url)
    
    if not text:
        print("Failed to extract text from the URL")
        sys.exit(1)
    
    # Generate recipe guide
    print("\nGenerating recipe guide...")
    recipe_guide = generate_recipe_guide(text)
    
    if recipe_guide:
        print("\nRecipe Guide:")
        print("-" * 50)
        print(recipe_guide)
    else:
        print("Failed to generate recipe guide")

if __name__ == "__main__":
    main()

