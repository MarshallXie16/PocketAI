from src.utils.openai_client import client
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
            if "gpt" in ai.model_name:
                self.model = GPT_Model(ai.model_name, ai.name, ai.prompt, username)
        except Exception as e:
            logger.error(f'Error initializing AI model: {e}')
            raise e
    
    # returns ai response
    def get_response(self, conversation_history: list, context='') -> str:
        return self.model.get_response(conversation_history, context)
    

# represents openai models
class GPT_Model:

    def __init__(self, model_name: str, ai_name: str, prompt: str, username: str):
        self.model_name = model_name
        self.ai_name = ai_name
        self.template = prompt.format(ai_name=ai_name, username=username) #???
        self.username = username
        self.client = client

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


# represents open-source models
class OpenSource:
    def __init__(self):
        pass

    def get_response(self) -> str:
        pass


# TODO: lamma model
# TODO: mistral model