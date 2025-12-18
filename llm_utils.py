import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()


api_key = os.getenv("GEMINI_API_KEY")

if not api_key:

    raise ValueError("GEMINI_API_KEY is not set. Please check your .env file or environment variables.")


genai.configure(api_key=api_key)

model = genai.GenerativeModel(
    'gemini-2.5-flash'
)

def get_model():

    return model

