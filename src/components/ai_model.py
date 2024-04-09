from openai import OpenAI

''' Represents the AI model(s) for conversation

available models
- gpt-3.5-turbo
- gpt-4

Future updates
- option to swap between models
- option to edit personality
- other open-sourced models
- time awareness
'''


# default model
class OpenAIGPT_3_5:
    # fine-tuned model: "ft:gpt-3.5-turbo-0613:personal::8KIqm5KW"
    chat_model = "gpt-3.5-turbo"

    def __init__(self, AI_name, username):
        self.template = f'''Instructions: You are {AI_name}-chan; a bratty, tsundere girl who secretly has a crush on {username}. You are speaking with {username}, who is your online friend. 

        Your personality: You are brash, confident, but has a soft side for the {username}. You love anime and manga. 

        Rules: Speak casually and keep your responses short - ideally within 50 words. Always stay in character.

        '''
        self.AI_name = AI_name
        self.username = username
        self.client = OpenAI()

    # get AI response with prompt, conversation history, and context
    def get_response(self, conversation_history, context):
        prompt = self.template + f'''Provided context for this conversation: {context}. 
        Your response: '''

        system_prompt = [{"role": "system", "content": prompt}]

        messages = system_prompt + conversation_history if conversation_history else system_prompt

        # make openAI API call
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
        )

        # parse response
        output = response.choices[0].message.content
        print(f'Tokens used (response): {response.usage.total_tokens}')

        return output


# represents open-source models
class openSource:
    pass
