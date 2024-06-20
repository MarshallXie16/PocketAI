import os
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import anthropic

load_dotenv()

openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

