from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from scheduler_app.models import MeetingBooking, User
from scheduler_app.serializers import MeetingBookingSerializer
from django.db.models import Q  # Import Q for complex lookups
import jwt
from decouple import config
from rest_framework.exceptions import AuthenticationFailed
import datetime

# Constants for error messages
TOKEN_EXPIRED = "Token expired"
INVALID_TOKEN = "Invalid token"

# Function to verify the JWT token
def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, config('mysecret'), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed(TOKEN_EXPIRED)
    except jwt.InvalidTokenError:
        raise AuthenticationFailed(INVALID_TOKEN)

@api_view(['POST'])
def list_user_meetings(request):
    user_id = request.data.get('user_id')

    if not user_id:
        return Response({"error":"User ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Get the Authorization token from the request headers
    if request.META.get('HTTP_AUTHORIZATION') is not None:
        token = request.META.get('HTTP_AUTHORIZATION').split(' ')[1]
        # Verify the JWT token
        decoded_payload = verify_jwt_token(token)
        
        # Extract the user email from the decoded token payload
        user_email = decoded_payload['email']

        try:
            # Fetch the user object
            user = get_object_or_404(User, id=user_id)
            
            # Get meetings where the user is a mandatory or optional attendee
            meetings = MeetingBooking.objects.filter(
                Q(mandatory_attendees__icontains=user.full_name) | 
                Q(optional_attendees__icontains=user.full_name)
            )
            
            # Serialize the meetings
            serializer = MeetingBookingSerializer(meetings, many=True)
            
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    else:
        return Response({"status": INVALID_TOKEN}, status=status.HTTP_401_UNAUTHORIZED)


