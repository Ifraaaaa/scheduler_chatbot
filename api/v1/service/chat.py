import requests
import logging
import re
from django.http import JsonResponse
from rest_framework.decorators import api_view
from django.utils import timezone
from scheduler_app.models import MeetingBooking, User
from dateutil import parser

# Set up logging
logger = logging.getLogger(__name__)

# Use a dictionary to track user sessions and details
user_sessions = {}

def extract_meeting_details(text):
    """
    Extract meeting details (attendee name, date, and time) from the user's message.
    """
    # Regular expression patterns for extracting names, dates, and times
    name_pattern = r'with\s+(\w+)'  # Matches "with John"
    date_pattern = r'(\d{1,2}(?:st|nd|rd|th)?\s+\w+)'  # Matches dates like "7th May"
    time_pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm)|(\d{1,2}\s*(?:am|pm)))'  # Matches times like "5 pm" or "5:30 pm"

    # Extract attendee name
    name_match = re.search(name_pattern, text)
    attendee_name = name_match.group(1) if name_match else None

    # Extract date
    date_match = re.search(date_pattern, text)
    meeting_date_str = date_match.group(0) if date_match else None

    # Extract time
    time_match = re.search(time_pattern, text)
    meeting_time_str = time_match.group(0) if time_match else None

    # Combine date and time into a single datetime object
    meeting_datetime = None
    if meeting_date_str and meeting_time_str:
        meeting_datetime_str = f"{meeting_date_str} {meeting_time_str}"
        meeting_datetime = parser.parse(meeting_datetime_str)

    return {
        'attendee_name': attendee_name,
        'meeting_datetime': meeting_datetime
    }

@api_view(['POST'])
def schedule_meeting(request):
    user_id = request.data.get('user_id')
    user_message = request.data.get('user_message')

    # Ensure the user exists
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("User not found.")
        return JsonResponse({'error': 'User not found.'}, status=404)

    # Initialize or retrieve the user's session
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'meeting_details': {},
            'state': 'awaiting_initial_info'
        }

    session_data = user_sessions[user_id]

    # Extract meeting details from the user's message
    extracted_details = extract_meeting_details(user_message)
    
    attendee_name = extracted_details['attendee_name']
    meeting_datetime = extracted_details['meeting_datetime']

    # Update session data with extracted details
    if attendee_name:
        session_data['meeting_details']['attendee'] = attendee_name
    if meeting_datetime:
        session_data['meeting_details']['meeting_date'] = meeting_datetime.date()
        session_data['meeting_details']['meeting_time'] = meeting_datetime.time()

    # Check if all meeting details have been provided
    if 'attendee' in session_data['meeting_details'] and \
       'meeting_date' in session_data['meeting_details'] and \
       'meeting_time' in session_data['meeting_details']:
        
        # All details are complete, create the meeting booking
        meeting_booking = MeetingBooking(
            user=user,
            meeting_date=session_data['meeting_details']['meeting_date'],
            meeting_time=session_data['meeting_details']['meeting_time'],
            mandatory_attendees=session_data['meeting_details']['attendee'],
            venue='online',  # Default value for venue
            status=False  # Mark as pending if some info is missing
        )
        
        meeting_booking.save()  # Save to the database
        logger.info("MeetingBooking entry created successfully.")

        # Clear the session data after successful booking
        del user_sessions[user_id]

        return JsonResponse({
            'message': 'Meeting successfully scheduled.',
            'details': {
                'attendee': session_data['meeting_details'].get('attendee'),
                'date': str(session_data['meeting_details'].get('meeting_date')),
                'time': str(session_data['meeting_details'].get('meeting_time'))
            },
            'booking_id': meeting_booking.booking_id,
            'assistant_message': "Your meeting has been scheduled successfully."
        }, status=201)

    
    # If details are missing, request more information from the user and call chatbot API for guidance.
    else:
        # Prepare a response prompting the user for missing information
        missing_details = []
        
        if 'attendee' not in session_data['meeting_details']:
            missing_details.append("attendee name")
        
        if 'meeting_date' not in session_data['meeting_details']:
            missing_details.append("meeting date")
        
        if 'meeting_time' not in session_data['meeting_details']:
            missing_details.append("meeting time")
        
        missing_details_str = " and ".join(missing_details)

        # Call Chatbot API for guidance on what to ask next
        chatbot_payload = {
            "model": "models/merlinite-7b-lab-Q4_K_M.gguf",
            "messages": [
                {
                    "role": "user",
                    "content": f"I need to schedule a meeting but I'm missing some information: {missing_details_str}."
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
            assistant_message = f"Please provide the {missing_details_str} to complete your booking."

        return JsonResponse({
            'message': f'Please provide the {missing_details_str} to complete the meeting booking.',
            'details_provided': session_data['meeting_details'],
            'assistant_message': assistant_message,
        }, status=200)