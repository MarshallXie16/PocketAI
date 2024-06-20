from src.utils.AI_model_client import openai_client, genai, HarmCategory, HarmBlockThreshold, anthropic_client
from src.models.users import AIModel
import logging

logger = logging.getLogger(__name__)

''' Represents the AI model(s) for conversation

    available models
    - gpt-3.5-turbo
    - gpt-4-turbo
    - fine-tuned model: "ft:gpt-3.5-turbo-0613:personal::8KIqm5KW"

    Current Features
    - AI_model - wrapper class for ai_models
    - each class represents a type of ai_model
    - use aiId to retrieve: ai name, model name, prompt
    - select model based on model name
    - inject prompt with username and ai name
    - run to get ai response

    Future updates
    - open sourced models
    - option to swap between models
    - option to edit prompt (personality)
    - time awareness (injected into model)
'''

# wrapper class for AI models
class AI_model:
    # constructor: initializes the correct model type based on ai_id
    def __init__(self, ai_id: int, username: str):
        # try to search for ai model in db
        try:
            ai = AIModel.query.filter_by(id=ai_id).first()
            if not ai:
                raise Exception("AI model not found")

            # select model based on model name
            if "gpt" in ai.model_name.lower():
                self.model = GPT(ai.model_name, ai.name, ai.prompt, username)
            elif "gemini" in ai.model_name.lower():
                self.model = Gemini(ai.model_name, ai.name, ai.prompt, username)
            elif "claude" in ai.model_name.lower():
                self.model = Claude(ai.model_name, ai.name, ai.prompt, username)
        except Exception as e:
            logger.error(f'Error initializing AI model: {e}')
            raise e
    
    # returns ai response
    def get_response(self, conversation_history: list, context='') -> str:
        return self.model.get_response(conversation_history, context)
    

# represents openai models
class GPT:

    def __init__(self, model_name: str, ai_name: str, prompt: str, username: str):
        self.model_name = model_name
        self.ai_name = ai_name
        self.template = prompt.format(ai_name=ai_name, username=username)
        self.username = username
        self.client = openai_client

    # get AI response with prompt, conversation history, and context
    def get_response(self, conversation_history: list, context: str) -> str:

        prompt = self.template + f''' You have the ability to interact with the user's calendar and email. Use html tags and symbols (br,  \\n, li, **) to format your response.'''

        system_prompt = [{"role": "system", "content": prompt}]
        
        conversation_history[-1]['content'] += f" Provided context for this conversation: {context}."

        messages = system_prompt + conversation_history if conversation_history else system_prompt

        print(f'messages: {messages}')
        
        # make openAI API call
        response = self.client.chat.completions.create(
            model=self.model_name or "gpt-3.5-turbo",
            messages=messages,
        )

        # parse response
        output = response.choices[0].message.content
        print(f'Tokens used (response): {response.usage.total_tokens}')

        return output


class Gemini:
    def __init__(self, model_name: str, ai_name: str, prompt: str, username: str):
        self.model = genai.GenerativeModel(model_name=model_name, 
                                           system_instruction=prompt.format(ai_name=ai_name, username=username) + f''' You have the ability to interact with the user's calendar and email. Use html tags and symbols (br,  \\n, li, **) to format your response.''',
                                           safety_settings={HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, 
                                                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                                                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                                                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE})
        self.ai_name = ai_name
        self.template = prompt.format(ai_name=ai_name, username=username) # this is redundant
        self.username = username
        self.client = openai_client

    def get_response(self, conversation_history: list, context: str) -> str:

        conversation_history[-1]['content'] += f" Provided context for this conversation: {context}."

        messages = gpt_to_gemini(conversation_history)
        
        response = self.model.generate_content(messages)

        print(f'Finish Reason: {response.candidates[0].finish_reason}')
        print(f'Token Count: {response.usage_metadata.total_token_count}')

        return response.text


class Claude:

    def __init__(self, model_name: str, ai_name: str, prompt: str, username: str):

        if "haiku" in model_name:
            self.model_name = "claude-3-haiku-20240307"
        elif "opus" in model_name:
            self.model_name = "claude-3-opus-20240229"
        else:
            self.model_name = 'claude-3-haiku-20240307'

        self.ai_name = ai_name
        self.template = prompt.format(ai_name=ai_name, username=username)
        self.username = username
        self.client = anthropic_client

    # get AI response with prompt, conversation history, and context
    def get_response(self, conversation_history: list, context: str) -> str:

        prompt = self.template + f''' You have the ability to interact with the user's calendar and email. Use html tags and symbols (br,  \\n, li, **) to format your response.'''
        
        conversation_history[-1]['content'] += f" Provided context for this conversation: {context}."
        
        response = self.client.messages.create(
            model=self.model_name or "claude-3-haiku-20240307",
            system=prompt,
            max_tokens=1000,
            messages=conversation_history
        )

        print(f'Stop Reason: {response.stop_reason}')
        print(f'Tokens (used): {response.usage.input_tokens + response.usage.output_tokens}' )

        return response.content[0].text


# represents open-source models
class OpenSource:
    def __init__(self):
        pass

    def get_response(self) -> str:
        pass


def gpt_to_gemini(gpt_context):
    gemini_context = []
    for message in gpt_context:
        role = message['role']
        content = message['content']
        
        if role == 'user':
            gemini_context.append({"role": "user", "parts": [content]})
        elif role == 'assistant':
            gemini_context.append({"role": "model", "parts": [content]})
    
    return gemini_context



# TODO: lamma model
# TODO: mistral model