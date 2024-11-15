import re
from datetime import datetime, timedelta
from django.http import JsonResponse
from rest_framework.decorators import api_view
from scheduler_app.models import MeetingBooking, User
import requests
import logging

# Set up logging
logger = logging.getLogger(__name__)

def parse_relative_date(date_str):
    """
    Parse relative date terms like 'today', 'tomorrow', 'upcoming' into actual dates.
    """
    current_date = datetime.now()
    if date_str.lower() == "today":
        return current_date
    elif date_str.lower() == "tomorrow":
        return current_date + timedelta(days=1)
    elif date_str.lower() == "upcoming":
        return current_date + timedelta(days=7)  # This can be customized to any specific logic
    return None

def extract_meeting_details(user_message):
    """
    Extract attendee name, date, and time from the user's message, handling relative terms like 'today', 'tomorrow', etc.
    """
    # Extract attendee name using regex
    name_pattern = r'with\s+([A-Za-z]+)'  # Match "with Sheena"
    date_pattern = r'(\b\d{1,2}(?:th|st|nd|rd)?\s*\w+\b|\b\w+\s+\d{1,2}\b|\b(today|tomorrow|upcoming)\b)'  # Matches specific dates like "20th November", "November 20", "today", "tomorrow"
    time_pattern = r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))'  # Match time like "at 11:00 pm"

    attendee_match = re.search(name_pattern, user_message)
    attendee_name = attendee_match.group(1) if attendee_match else None

    # Extract specific date from user message (e.g., "20th November", "tomorrow", "November 20")
    date_match = re.search(date_pattern, user_message)
    meeting_date = None
    if date_match:
        date_str = date_match.group(1).strip()
        
        # Handle relative terms like today, tomorrow, upcoming
        meeting_date = parse_relative_date(date_str)
        
        if not meeting_date:
            # Try to handle regular date formats
            try:
                # Handle dates like "20th November" or "November 20"
                meeting_date = datetime.strptime(date_str, "%d %B")
            except ValueError:
                try:
                    meeting_date = datetime.strptime(date_str, "%B %d")
                except ValueError:
                    meeting_date = None

        # Set the year to the current year
        if meeting_date:
            meeting_date = meeting_date.replace(year=datetime.now().year)

    # Extract time from user message
    time_match = re.search(time_pattern, user_message)
    meeting_time = None
    if time_match:
        time_str = time_match.group(1).strip().lower()
        meeting_time = datetime.strptime(time_str, '%I %p').time() if ':' not in time_str else datetime.strptime(time_str, '%I:%M %p').time()

    return {
        'attendee_name': attendee_name,
        'meeting_date': meeting_date,
        'meeting_time': meeting_time
    }

@api_view(['POST'])
def edit_meeting(request):
    user_id = request.data.get('user_id')
    user_message = request.data.get('user_message')

    # Ensure the user exists
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("User not found.")
        return JsonResponse({'error': 'User not found.'}, status=404)

    # Extract meeting details from the user's message
    meeting_details = extract_meeting_details(user_message)
    attendee_name = meeting_details['attendee_name']
    meeting_date = meeting_details['meeting_date']
    meeting_time = meeting_details['meeting_time']

    if not meeting_date or not meeting_time:
        return JsonResponse({
            'error': 'Could not extract a valid date or time from the message.'
        }, status=400)

    # Fetch all meetings for the user
    meetings = MeetingBooking.objects.filter(user=user)

    if not meetings.exists():
        return JsonResponse({'error': 'No meetings found for the user.'}, status=404)

    # Find the matching meeting (this logic could be customized based on actual use case)
    matching_meeting = meetings.filter(mandatory_attendees__icontains=attendee_name).first()

    if not matching_meeting:
        return JsonResponse({'error': 'No matching meeting found.'}, status=404)

    # Update meeting details
    matching_meeting.meeting_date = meeting_date.date()
    matching_meeting.meeting_time = meeting_time
    matching_meeting.mandatory_attendees = attendee_name
    matching_meeting.save()

    # Prepare assistant response
    assistant_message = (
        f"Thank you for updating us on the new date and time for your meeting. "
        f"I have noted that it will be held on {meeting_date.strftime('%B %d, %Y')}, "
        f"at {meeting_time.strftime('%I:%M %p')}. If there are any other details or "
        f"arrangements that need to be discussed, please let me know so that I can "
        f"ensure everything is in order for the meeting."
    )

    # Send confirmation message using a chatbot or internal API
    chatbot_payload = {
        "model": "models/merlinite-7b-lab-Q4_K_M.gguf",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": f"User has requested to reschedule the meeting with {attendee_name} "
                           f"to {meeting_date.strftime('%Y-%m-%d')} at {meeting_time.strftime('%I:%M %p')}."
            }
        ]
    }

    try:
        chatbot_url = "http://127.0.0.1:8000/v1/chat/completions"
        chatbot_response = requests.post(chatbot_url, json=chatbot_payload)
        chatbot_response.raise_for_status()
        chatbot_data = chatbot_response.json()
        assistant_message = chatbot_data['choices'][0]['message']['content']
    except requests.RequestException as e:
        logger.error(f"Chatbot API request failed: {str(e)}")
        assistant_message = "Meeting has been rescheduled."

    return JsonResponse({
        'message': 'Meeting successfully rescheduled.',
        'assistant_message': assistant_message,
        'meeting_id': matching_meeting.booking_id,
        'meeting_date': str(matching_meeting.meeting_date),
        'meeting_time': str(matching_meeting.meeting_time),
        'attendee_names': matching_meeting.mandatory_attendees
    }, status=200)
