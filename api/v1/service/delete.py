import requests
import logging
import re
from datetime import datetime, timedelta
from django.http import JsonResponse
from rest_framework.decorators import api_view
from scheduler_app.models import MeetingBooking, User

# Set up logging
logger = logging.getLogger(__name__)

def extract_meeting_details(text):
    """
    Extract meeting details (attendee name, meeting date) from the user's message.
    """
    # Patterns for extracting date and attendee name
    name_pattern = r'with\s+(\w+)'  # Matches "with John"
    date_pattern = r'(\d{1,2}(?:st|nd|rd|th)?\s+of\s+\w+|\btomorrow\b|\bupcoming\b)'  # Matches dates like "7th of November", "tomorrow", or "upcoming"

    # Extract attendee name
    name_match = re.search(name_pattern, text)
    attendee_name = name_match.group(1) if name_match else None

    # Extract date
    date_match = re.search(date_pattern, text)
    meeting_date = None

    if date_match:
        date_str = date_match.group(1).lower()
        today = datetime.today()

        # Handle "tomorrow"
        if 'tomorrow' in date_str:
            meeting_date = today + timedelta(days=1)
        # Handle specific dates like "7th of November"
        else:
            try:
                meeting_date = datetime.strptime(date_str, '%dth of %B')
                meeting_date = meeting_date.replace(year=today.year)  # Assume current year
            except ValueError:
                meeting_date = None  # Keep None if parsing fails

    return {
        'attendee_name': attendee_name,
        'meeting_date': meeting_date
    }

@api_view(['POST'])
def delete_meeting(request):
    user_id = request.data.get('user_id')
    user_message = request.data.get('user_message')

    # Ensure the user exists
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("User not found.")
        return JsonResponse({'error': 'User not found.'}, status=404)

    # Extract meeting details from the user's message
    extracted_details = extract_meeting_details(user_message)
    attendee_name = extracted_details['attendee_name']
    meeting_date = extracted_details['meeting_date']

    # Fetch all meetings for the user
    meetings = MeetingBooking.objects.filter(user=user)

    if not meetings.exists():
        return JsonResponse({'error': 'No meetings found for the user.'}, status=404)

    # Filter meetings based on the extracted details
    matching_meeting = None

    for meeting in meetings:
        mandatory_attendees = meeting.mandatory_attendees.lower() if meeting.mandatory_attendees else ""

        # Match the attendee name if provided
        if attendee_name and attendee_name.lower() not in mandatory_attendees:
            continue

        # Match the meeting date if provided
        if meeting_date and meeting.meeting_date != meeting_date.date():
            continue

        # If "upcoming" was mentioned or no specific date, consider the next meeting
        if 'upcoming' in user_message.lower():
            upcoming_meetings = meetings.filter(meeting_date__gte=datetime.today()).order_by('meeting_date')
            if upcoming_meetings.exists():
                matching_meeting = upcoming_meetings.first()
            break

        # If all checks pass, this is the matching meeting
        matching_meeting = meeting
        break

    if not matching_meeting:
        return JsonResponse({'error': 'No matching meeting found.'}, status=404)

    # Mark the meeting as deleted (soft delete)
    matching_meeting.status = False
    matching_meeting.save()

    # Call Chatbot API for confirmation message
    chatbot_payload = {
        "model": "models/merlinite-7b-lab-Q4_K_M.gguf",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": f"User has requested to delete the meeting with {attendee_name if attendee_name else 'unknown attendee'}. The meeting was scheduled on {matching_meeting.meeting_date} at {matching_meeting.meeting_time}. Please confirm the deletion."
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
        assistant_message = f"Meeting has been deleted."

    return JsonResponse({
        'message': f'Meeting successfully deleted.',
        'assistant_message': assistant_message,
        'meeting_id': matching_meeting.booking_id,
        'meeting_date': str(matching_meeting.meeting_date),
        'meeting_time': str(matching_meeting.meeting_time)
    }, status=200)
