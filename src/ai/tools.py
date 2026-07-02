"""Tool declarations and dispatch for the agent loop.

Declarations use Anthropic's ``input_schema`` JSON-Schema format as the
neutral house format; adapters translate for OpenAI/Gemini. Dates are RFC3339
strings produced by the model — the system prompt always includes the current
date/time and the user's timezone, which is what makes that reliable. The
old date-reference enum cascade (context_analyzer + utils.parse_date) is
retired.

Every dispatch is scoped by user_id — tools can only touch the calling
user's data. Tool failures return an error STRING to the model (never
raise): the model should apologize/adjust, not 500 the request.
"""

import datetime
import logging

from src.ai import memory
from src.services.integrations.calendar_service import GoogleCalendar
from src.services.integrations.email_service import Gmail

logger = logging.getLogger(__name__)

_calendar = GoogleCalendar()
_gmail = Gmail()

TOOLS = [
    {
        'name': 'memory_search',
        'description': (
            'Search your long-term memory of this user for relevant past '
            'conversations, facts, and shared moments. Call this when the user '
            'references something from the past, when personal context would '
            'improve your reply, or when you are asked what you remember.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'What to recall, phrased as a description of the situation or fact.'},
            },
            'required': ['query'],
        },
    },
    {
        'name': 'calendar_read',
        'description': (
            "Read the user's Google Calendar. Call this whenever the user asks "
            'about their schedule, events, plans, or availability. Times are '
            "RFC3339 with timezone offset (e.g. '2026-07-02T09:00:00-07:00')."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'start': {'type': 'string', 'description': 'Range start, RFC3339 with offset.'},
                'end': {'type': 'string', 'description': 'Range end, RFC3339 with offset.'},
                'event_name': {'type': 'string', 'description': 'Optional: search for events matching this name.'},
                'availability': {'type': 'boolean', 'description': 'Optional: true to return free time slots instead of events.'},
            },
            'required': ['start', 'end'],
        },
    },
    {
        'name': 'calendar_create',
        'description': (
            "Create an event on the user's Google Calendar. Call this when the "
            'user asks to schedule, book, or add something. Confirm ambiguous '
            'details (date, time) with the user BEFORE calling.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'start': {'type': 'string', 'description': 'Event start, RFC3339 with offset.'},
                'end': {'type': 'string', 'description': 'Event end, RFC3339 with offset.'},
                'description': {'type': 'string'},
                'recurrence': {'type': 'string', 'enum': ['weekly', 'monthly'], 'description': 'Optional recurring frequency.'},
            },
            'required': ['title', 'start', 'end'],
        },
    },
    {
        'name': 'email_read',
        'description': (
            "Read the user's Gmail inbox. Call this when the user asks about "
            'their email. Optionally filter by sender name and/or subject.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'start': {'type': 'string', 'description': 'Range start, RFC3339 with offset.'},
                'end': {'type': 'string', 'description': 'Range end, RFC3339 with offset.'},
                'sender_name': {'type': 'string'},
                'subject': {'type': 'string'},
            },
            'required': ['start', 'end'],
        },
    },
    {
        'name': 'email_send',
        'description': (
            "Draft an email to send from the user's Gmail. The recipient can "
            "be a contact's name (looked up in the user's contacts) or an "
            'explicit email address. This does NOT send immediately — it '
            'stores a draft; show the draft to the user, and after they '
            'confirm in their next message, call confirm_action.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'recipient_name': {'type': 'string', 'description': "Contact name to look up (or the recipient's name if recipient_email is given)."},
                'recipient_email': {'type': 'string', 'description': 'Explicit email address; overrides contact lookup.'},
                'subject': {'type': 'string'},
                'body': {'type': 'string'},
            },
            'required': ['recipient_name', 'subject', 'body'],
        },
    },
    {
        'name': 'schedule_checkin',
        'description': (
            'Schedule yourself to reach out to the user at a future moment. '
            'Call this when the user makes a commitment ("I\'ll sleep by 11 '
            'tonight!") or mentions something worth following up on (an '
            'interview, an appointment, a hard day coming). Pick a thoughtful '
            'time — e.g. the morning after a commitment, or an hour before a '
            'big event. Mention to the user that you\'ll check in.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'when': {'type': 'string', 'description': 'When to reach out, RFC3339 with offset.'},
                'reason': {'type': 'string', 'description': 'Why — this is your note to your future self about what to say.'},
            },
            'required': ['when', 'reason'],
        },
    },
    {
        'name': 'confirm_action',
        'description': (
            'Execute the pending calendar_create or email_send draft AFTER '
            'the user has explicitly confirmed it in a message sent after '
            'the draft was shown. Call with no arguments. If the user asked '
            'for changes instead, call the drafting tool again with new '
            'arguments (this replaces the pending draft).'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
    },
]

# Tools that change the outside world — they draft first, execute on
# confirm_action. The gate is server-side: confirmation is only honored if a
# genuine user message arrived AFTER the draft was stored, so injected
# content (e.g. a hostile email the model just read) cannot draft and
# confirm within the same turn.
CONSEQUENTIAL_TOOLS = {'calendar_create', 'email_send'}


def _parse_rfc3339(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value)


def _latest_message_id(user_id: int, ai_id: int) -> int:
    from src.models.message import Message

    row = Message.query.filter_by(user_id=user_id, ai_id=ai_id).order_by(Message.id.desc()).first()
    return row.id if row else 0


def _store_draft(name: str, args: dict, *, user_id: int, ai_id: int) -> str:
    """Store a consequential action as a pending draft (not executed)."""
    from src.extensions import db
    from src.models.conversation_state import ConversationState

    state = ConversationState.get_or_create(user_id, ai_id)
    state.pending_action = {'tool': name, 'args': args, 'message_id': _latest_message_id(user_id, ai_id)}
    db.session.commit()

    if name == 'email_send':
        summary = (f"To: {args.get('recipient_email') or args['recipient_name']}\n"
                   f"Subject: {args.get('subject', '')}\nBody: {args['body']}")
    else:
        summary = f"{args['title']} — {args['start']} to {args['end']}"
    return (f'Draft stored (NOT executed yet):\n{summary}\n\n'
            'Show this draft to the user. If they confirm in their next '
            'message, call confirm_action to execute it.')


def _confirm_action(*, user_id: int, ai_id: int, user_timezone: str) -> str:
    """Execute the pending draft — only if the user replied after it was made."""
    from src.extensions import db
    from src.models.conversation_state import ConversationState
    from src.models.message import Message

    state = ConversationState.get_or_create(user_id, ai_id)
    pending = state.pending_action
    if not pending:
        return 'There is no pending action to confirm.'

    # Server-side gate: a genuine USER message must exist after the draft.
    confirmed_by_user = Message.query.filter(
        Message.user_id == user_id,
        Message.ai_id == ai_id,
        Message.sender == 'user',
        Message.id > pending.get('message_id', 0),
    ).first()
    if not confirmed_by_user:
        return ('Cannot execute yet: the user has not replied since this draft '
                'was created. Show them the draft and wait for their answer.')

    tool, args = pending['tool'], pending['args']
    state.pending_action = None
    db.session.commit()
    return _execute(tool, args, user_id=user_id, user_timezone=user_timezone)


def _execute(name: str, args: dict, *, user_id: int, user_timezone: str) -> str:
    """Actually perform a consequential action (post-confirmation)."""
    if name == 'calendar_create':
        service = _calendar.authenticate(user_id)
        event = {
            'summary': args['title'],
            'description': args.get('description', ''),
            'start': {'dateTime': args['start'], 'timeZone': user_timezone},
            'end': {'dateTime': args['end'], 'timeZone': user_timezone},
        }
        if args.get('recurrence') == 'weekly':
            event['recurrence'] = ['RRULE:FREQ=WEEKLY']
        elif args.get('recurrence') == 'monthly':
            event['recurrence'] = ['RRULE:FREQ=MONTHLY']
        created = service.events().insert(calendarId='primary', body=event).execute()
        return (
            f"Event created: {args['title']} ({args['start']} to {args['end']}). "
            f"Link: {created.get('htmlLink', 'n/a')}"
        )

    if name == 'email_send':
        return _gmail.send_email(
            user_id,
            'send',
            args['recipient_name'],
            args['body'],
            recipient_email=args.get('recipient_email'),
            subject=args.get('subject'),
        )

    return f'Unknown pending action: {name}'


def dispatch(name: str, args: dict, *, user_id: int, ai_id: int, user_timezone: str = 'UTC') -> str:
    """Execute a tool call and return its result as a string for the model."""
    try:
        if name == 'memory_search':
            results = memory.search_memory(user_id, ai_id, args['query'])
            if not results:
                return 'No relevant memories found.'
            return 'Relevant memories:\n- ' + '\n- '.join(results)

        if name == 'calendar_read':
            service = _calendar.authenticate(user_id)
            if args.get('event_name'):
                result, _ = _calendar.find_event(service, args['start'], args['end'], args['event_name'])
            elif args.get('availability'):
                result, _ = _calendar.check_availability(service, args['start'], args['end'])
            else:
                result, _ = _calendar.list_events(service, args['start'], args['end'])
            return result

        if name == 'email_read':
            service = _gmail.authenticate(user_id)
            start = _parse_rfc3339(args['start'])
            end = _parse_rfc3339(args['end'])
            if args.get('sender_name') or args.get('subject'):
                return _gmail.search_inbox(service, start, end, args.get('sender_name'), args.get('subject'),
                                           user_id=user_id)
            return _gmail.list_emails(service, start, end)

        if name == 'schedule_checkin':
            from src.services import proactive_service

            row = proactive_service.schedule_checkin(user_id, ai_id, args['when'], args['reason'])
            return (f'Check-in scheduled for {row.scheduled_for.isoformat()} UTC. '
                    'It will only be sent if the user has proactive messages enabled.')

        if name in CONSEQUENTIAL_TOOLS:
            return _store_draft(name, args, user_id=user_id, ai_id=ai_id)

        if name == 'confirm_action':
            return _confirm_action(user_id=user_id, ai_id=ai_id, user_timezone=user_timezone)

        return f"Unknown tool: {name}"

    except Exception:
        # Full details go to the log only — exception text can carry API
        # internals we don't want echoed to the model/user.
        logger.exception('Tool %s failed (user=%s)', name, user_id)
        return (f"The {name} tool hit an internal error and returned nothing. "
                'Tell the user plainly that it did not work and suggest trying again later.')
