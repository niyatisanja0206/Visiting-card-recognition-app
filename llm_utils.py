import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY is not set. Please check your .env file or environment variables.")

genai.configure(api_key=api_key)


MODEL_NAME = 'gemini-2.5-flash'  

# Initialize the model
model = genai.GenerativeModel(MODEL_NAME)

def get_model():
    """
    Get the configured Gemini model instance.
    Returns:
        GenerativeModel: Configured Gemini model instance
    """
    return model
