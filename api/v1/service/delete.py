from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from scheduler_app.models import MeetingBooking, User
import jwt
from decouple import config
from rest_framework.exceptions import AuthenticationFailed
import datetime

# Constants for error messages
TOKEN_EXPIRED = "Token expired"
INVALID_TOKEN = "Invalid token"
MEETING_NOT_FOUND = "Meeting not found"
MEETING_ALREADY_DELETED = "Meeting already deleted"

# Function to verify the JWT token
def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, config('mysecret'), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed(TOKEN_EXPIRED)
    except jwt.InvalidTokenError:
        raise AuthenticationFailed(INVALID_TOKEN)

@api_view(['DELETE'])
def delete_meeting(request):
    # Extract the meeting_id from the request
    meeting_id = request.data.get('meeting_id')
    
    if not meeting_id:
        return Response({"error": "Meeting ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Get the Authorization token from the request headers
    if request.META.get('HTTP_AUTHORIZATION') is not None:
        token = request.META.get('HTTP_AUTHORIZATION').split(' ')[1]
        # Verify the JWT token
        decoded_payload = verify_jwt_token(token)
        
        # Extract the user email from the decoded token payload
        user_email = decoded_payload['email']

        try:
            # Find the user by email
            user = User.objects.get(email=user_email)

            # Find the meeting by meeting_id and user
            meeting = MeetingBooking.objects.filter(booking_id=meeting_id, user=user).first()
            if not meeting:
                return Response({"error": MEETING_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

            # Check if the meeting has already been deleted (status is False)
            if not meeting.status:
                return Response({"error": MEETING_ALREADY_DELETED}, status=status.HTTP_400_BAD_REQUEST)

            # Set the meeting status to False (soft delete)
            meeting.status = False
            meeting.save()

            return Response({"message": "Meeting successfully deleted."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    else:
        return Response({"status": INVALID_TOKEN}, status=status.HTTP_401_UNAUTHORIZED)
