import google.genai as genai
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:

    raise ValueError("GEMINI_API_KEY is not set. Please check your .env file or environment variables.")


client = genai.Client(api_key=api_key)

MODEL_NAME = 'gemini-2.5-flash'

class ModelWrapper:
    def __init__(self, client, model_name):
        self.client = client
        self.model_name = model_name

    def generate_content(self, contents):
        return self.client.models.generate_content(
            model=self.model_name,
            contents=contents
        )

def get_model():
    return ModelWrapper(client, MODEL_NAME)
