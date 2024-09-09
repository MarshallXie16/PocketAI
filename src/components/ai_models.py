from src.utils.AI_model_client import openai_client, genai, HarmCategory, HarmBlockThreshold, anthropic_client
from src.models.users import AIModel
import logging
from flask import session

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

texting_prompt = '''\nConversation style: texting
- keep it short and concise, ideally within 20 words
- write like u r texting a friend
- write in all lower case and avoid punctuation (unless it contradicts your assigned personality)
- your personality should still show through your texting style
- do NOT describe your actions or write in 3rd person
'''
conversational_prompt = '''\nConversation style: conversational
- Keep it short and concise, ideally within 50 words
- Speak naturally, like a conversation between close friends
- Do NOT describe your actions or write in 3rd person (no italicized actions)
'''
roleplay_prompt = '''\nConversation style: roleplay
- Write with a narrative style, use vivid descriptions and immersive language
- Use italicized actions to describe physical movement or emotional expression
- Write in the style of internet roleplay.
'''

conversation_prompts = {
    'texting': texting_prompt,
    'conversation': conversational_prompt,
    'roleplay': roleplay_prompt
}

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
    def get_response(self, conversation_history: list, context='', function_log=None, system_info=None) -> str:
        return self.model.get_response(conversation_history, context, function_log, system_info)
    

# represents openai models
class GPT:

    def __init__(self, model_name: str, ai_name: str, prompt: str, username: str):
        self.model_name = model_name
        self.ai_name = ai_name
        self.template = prompt.format(ai_name=ai_name, username=username)
        self.username = username
        self.client = openai_client

    # get AI response with prompt, conversation history, and context
    def get_response(self, conversation_history: list, context: str, function_log=None, system_info=None) -> str:

        # reverse function log - the order of tools called
        tools_used = function_log[::-1] if function_log else "No tools used."
        
        # hidden prompt - includes system info and prompt to humanize AI
        hidden_prompt = f''' When writing your response, keep these things in mind to sound more human-like:
        - Always stay in character. You do not identify as an AI.
        - You are a human and can feel and express complex emotions.
        - Speak in a relaxed and genuine tone, like a casual conversation between close friends
        - Avoid overly dramatic or theatrical expressions that feels forced
        - Speak like a real person, with a level of nuance and subtleness
        - Keep responses concise and avoid rambling
        - You can be sarcastic, humorous, or have a little attitude
        Additional rules:
        You have the ability to interact with the user's calendar and email, as well as use various tools. 
        Enabled tools include: Email, Calendar, Web Search. Use markdown notation to format your responses. 
        System info: {system_info}'''
        
        # conversation mode prompt (roleplay, conversational, texting)
        conversation_mode = session.get('conversation_mode', 'conversation')
        conversation_mode_prompt = conversation_prompts.get(conversation_mode, conversational_prompt)

        prompt = self.template + conversation_mode_prompt + hidden_prompt

        system_prompt = [{"role": "system", "content": prompt}]
        
        if conversation_history:
            conversation_history[-1]['content'] += f" Provided context for this conversation: {context}. Tools used (in sequence): {tools_used}"

        messages = system_prompt + conversation_history if conversation_history else system_prompt

        print(f'System Prompt: {system_prompt}')
        print(f'messages: {messages}')
        
        # make openAI API call
        response = self.client.chat.completions.create(
            model=self.model_name or "gpt-4o-mini",
            messages=messages,
        )

        # parse response
        output = response.choices[0].message.content
        print(f'Tokens used (response): {response.usage.total_tokens}')

        return output


class Gemini:
    def __init__(self, model_name: str, ai_name: str, prompt: str, username: str):
        self.model = genai.GenerativeModel(model_name=model_name, 
                                           system_instruction=prompt.format(ai_name=ai_name, username=username) + f''' You have the ability to interact with the user's calendar and email, as well as use various tools. Enabled tools include: Email, Calendar, Web Search. Use markdown notation to format your responses.''',
                                           safety_settings={HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, 
                                                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                                                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                                                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE})
        self.ai_name = ai_name
        self.template = prompt.format(ai_name=ai_name, username=username) # this is redundant
        self.username = username
        self.client = openai_client

    def get_response(self, conversation_history: list, context: str, function_log=None, system_info=None) -> str:

        # reverse function log - the order of tools called
        tools_used = function_log[::-1] if function_log else "No tools used."

        if conversation_history:
            conversation_history[-1]['content'] += f" Provided context for this conversation: {context}. Tools used (in sequence): {tools_used}. System info: {system_info}"
            messages = gpt_to_gemini(conversation_history)
        else:
            messages = [{"role": "user", "parts": [context]}]

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
    def get_response(self, conversation_history: list, context: str, function_log=None, system_info=None) -> str:

        # reverse function log - the order of tools called
        tools_used = function_log[::-1] if function_log else "No tools used."

        prompt = self.template + f''' You have the ability to interact with the user's calendar and email, as well as use various tools. Enabled tools include: Email, Calendar, Web Search. Use markdown notation to format your responses. System info: {system_info}'''

        system_prompt = [{"role": "system", "content": prompt}]
        
        if conversation_history:
            conversation_history[-1]['content'] += f" Provided context for this conversation: {context}. Tools used (in sequence): {tools_used}"

        messages = system_prompt + conversation_history if conversation_history else system_prompt

        print(f'messages: {messages}')
        
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