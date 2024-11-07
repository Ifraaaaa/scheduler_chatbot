from rest_framework import serializers
from scheduler_app.models import MeetingBooking


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=5)
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'email']



class MeetingBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingBooking
        fields = ['booking_id', 'meeting_date', 'meeting_time', 'venue', 'mandatory_attendees', 'optional_attendees', 'status']
