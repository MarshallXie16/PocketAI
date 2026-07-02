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
            "Send an email from the user's Gmail. The recipient can be a "
            "contact's name (looked up in the user's contacts) or an explicit "
            'email address. ALWAYS show the user the draft and get their '
            'confirmation in conversation before calling this.'
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
]


def _parse_rfc3339(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value)


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

        if name == 'email_read':
            service = _gmail.authenticate(user_id)
            start = _parse_rfc3339(args['start'])
            end = _parse_rfc3339(args['end'])
            if args.get('sender_name') or args.get('subject'):
                return _gmail.search_inbox(service, start, end, args.get('sender_name'), args.get('subject'))
            return _gmail.list_emails(service, start, end)

        if name == 'email_send':
            return _gmail.send_email(
                user_id,
                'send',
                args['recipient_name'],
                args['body'],
                recipient_email=args.get('recipient_email'),
                subject=args.get('subject'),
            )

        return f"Unknown tool: {name}"

    except Exception as exc:
        logger.exception('Tool %s failed', name)
        return f"Tool '{name}' failed: {exc}. Explain the problem to the user and suggest what they can do."
