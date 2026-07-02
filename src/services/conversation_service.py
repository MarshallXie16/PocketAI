"""The chat turn: orchestrating an AI response.

``run_ai_response`` is the heart of it — it loads conversation history and
session memory, runs the legacy context-analyzer cascade for tool use, calls
the persona model, and flushes short-term memory into long-term (Pinecone)
memory on a cadence. This whole flow is replaced by the hand-rolled tool loop
in Phase 3; here it is only relocated, not rewritten.
"""

import datetime
import logging

import pytz
from flask import session
from flask_login import current_user

from src.components.ai_models import AI_model
from src.components.context_analyzer import context_analyzer
from src.components.memory import long_term_memory
from src.extensions import db
from src.models.message import Message
from src.utils.utils import utilities

logger = logging.getLogger(__name__)


def run_ai_response(ai_id, user_message):
    """Run a user message (with conversation history) through the selected AI
    model and return the response string."""

    # load session variables
    # TODO: rename these session variables
    memory_queue = session.get('memory_queue', [])
    memory_queue_count = session.get('memory_queue_count', 0)
    context_length = session.get('context_length', 6)
    memory_chunk_size = session.get('memory_chunk_size', 2)
    ai_name = session.get('ai_name', 'Assistant')

    # Settings for debugging
    logger.info('---- Settings ----')
    logger.debug(f'Memory Queue Count: {memory_queue_count}')
    logger.debug(f'Memory Queue:       {memory_queue}')
    logger.debug(f'Context length:     {context_length}')
    logger.info('------------------')

    # Instantiate AI model
    try:
        ai = AI_model(ai_id, current_user.username)
    except Exception as e:
        logger.error(f'Error: {e}')
        raise Exception('Failed to instantiate AI model.')

    # query and parse conversation history
    # TODO: keep track of conversation history in cache/session
    # TODO: limit conversation history based on token size as well (currently number of messages)
    try:
        conversation_history = Message.query.filter_by(user_id=current_user.id, ai_id=ai_id).order_by(
            Message.timestamp.desc()).limit(context_length).all()[::-1]
        latest_messages = [{'role': msg.sender, 'content': msg.message} for msg in conversation_history]
    except Exception as e:
        logger.error(f'Error: {e}')
        latest_messages = []

    # get system info
    system_info = get_system_info(session.get('user_timezone'))

    # analyze the context and determine intent (latest 6 messages)
    print_conversation_history(latest_messages)
    intention, is_function_call = context_analyzer.analyze_context(latest_messages)

    # if more context is needed, call a function
    if intention and is_function_call:
        context, function_log = context_analyzer.parse_func(intention, latest_messages, current_user.id, ai_id, system_info)
        logger.debug(f'Context: {context}')
        logger.debug(f'Function log: {function_log}')
        logger.info('---------------------------------')
    # clarification is needed but no functions were called
    elif intention:
        context = f'Seek clarification: {intention}'
        function_log = None
    # otherwise, no additional context is needed
    else:
        context = ''
        function_log = None

    # run ai response with the provided context (if any)
    response = ai.get_response(latest_messages, context=context, function_log=function_log, system_info=system_info)

    logger.debug(f'AI response: {response}')
    logger.debug(f'Message count: {memory_queue_count}/{memory_chunk_size}')
    logger.info('---------------------------------')

    # saves short-term memory to long-term memory every x message cycles
    if memory_queue_count >= memory_chunk_size:
        logger.debug(f'Short-term memory: {memory_queue}')
        # determine if message is important
        memory = utilities.summarize(memory_queue, ai_name, current_user.username)
        if memory.lower().strip() == 'false':
            logger.info('message not saved (not important).')
        elif memory:
            long_term_memory.save_memory(current_user.id, ai_id, memory)
            logger.info('message saved.')
        else:
            logger.info('message not saved (error).')
        memory_queue_count = 0
        memory_queue.clear()
    else:
        memory_queue_count += 1
        memory_queue.append(
            f'"{current_user.username}": {user_message}, {ai_name}: {response}')

    # update session variables
    session['memory_queue_count'] = memory_queue_count
    session['memory_queue'] = memory_queue
    session['past_context'] = context

    return response


def get_system_info(user_timezone):
    """Return the current date and time, formatted for the given timezone."""
    try:
        timezone = pytz.timezone(user_timezone)
        current_time = datetime.datetime.now(timezone)

        date_str = current_time.strftime('Today is %A, %b %d, %Y.')
        time_str = current_time.strftime('The current time is %I:%M%p.').lower()

        return f'{date_str} {time_str}'
    except Exception as e:
        logger.error(f'Error: {e}')
        return None


def update_conversation_history(user_id, ai_id, sender, message, voice_url=None):
    """Add a single message to the database. Returns its id."""
    message = Message(user_id=user_id, ai_id=ai_id, sender=sender, message=message, voice_url=voice_url)
    db.session.add(message)
    db.session.commit()
    return message.id


def print_conversation_history(conversation_history):
    """Log conversation history for debugging."""
    logger.info('---- Conversation History ----')
    for msg in conversation_history:
        logger.info(f"{msg['role']}: {msg['content']}")
    logger.info('-------------------------------')


def generate_welcome_message(ai_model, user):
    """Generate an in-character welcome message. Returns the string, or False on error."""
    welcome_prompt = 'This is the first time you are chatting with the user. Generate a welcome message for the user, in character.'
    try:
        tmp_model = AI_model(ai_model.id, user.username)
        return tmp_model.get_response(False, welcome_prompt)
    except Exception as e:
        logger.error(f'Error generating welcome message: {e}')
        return False
