from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv() # load environment variables from .env file
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)