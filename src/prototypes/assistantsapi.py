from openai import OpenAI
import time

client = OpenAI()


code_interpreter = {"type": "code_interpreter"}
retrieval = {"type": "retrieval"}
function_one = {
    "type": "function",
    "function": {
        "description": "Call this function if the user mentions calendar",
        "name": "calendar",
        "parameters": {
            "type": "object",
                "properties": {
                    "event": {
                        "type": "string",
                        "description": "The event to add to the user's calendar.",
                        },
                    },
                    "required": ["event"],
                }
    }

}

# Upload a file with an "assistants" purpose
file = client.files.create(
    file=open("knowledge.txt", "rb"),
    purpose='assistants'
)

assistant = client.beta.assistants.create(
    name="AI anime girl",
    instructions="You are a cute anime girl. Speak like one.",
    model="gpt-3.5-turbo-1106",
    tools=[code_interpreter, retrieval, function_one],
    file_ids=[file.id]
)

thread = client.beta.threads.create()

def initial_message():
    print("Assistant: Hello master, how may I help you today?")


# get ai output
# while true
# get user input
# get ai output
if __name__ == "__main__":

    while True:

        # get user input
        user_input = input("User: ")

        # special user commands
        if user_input.lower() == "exit":
            exit()

        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # execute the run
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id,

        )

        while True:
            # try retrieving the thread
            retrieved_thread = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

            # function call triggered
            if retrieved_thread.status == "requires_action":
                # parse function call
                func_info = retrieved_thread.required_action.submit_tool_outputs.tool_calls[0].function
                func_args = func_info.arguments
                func_name = func_info.name
                print("Function Called!")
                print(f'{func_name}: {func_args}')

                # do something cool with function call

                # return context and continue run
                run = client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=[
                        {
                            "tool_call_id": retrieved_thread.required_action.submit_tool_outputs.tool_calls[0].id,
                            "output": func_args,
                        }
                    ]
                )

            # normal operations
            if retrieved_thread.status == "completed":
                messages = client.beta.threads.messages.list(
                    thread_id=thread.id,
                    order="asc",
                    after=message.id
                )

                # parse message
                response = messages.data[0].content[0].text.value
                # print latest AI message
                print(f'Assistant: {response}')

                break