from django.db import models
import uuid
from django.utils import timezone
import datetime
import hashlib

class User(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    otp = models.CharField(max_length=32, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.email

    def generate_otp(self):
        import random
        otp = str(random.randint(10000, 99999))
        self.otp = hashlib.md5(otp.encode()).hexdigest()  # Hash the OTP
        self.otp_created_at = timezone.now()
        self.save()
        return otp  # Return the raw OTP for sending in email

    def is_otp_valid(self, otp):
        hashed_otp = hashlib.md5(otp.encode()).hexdigest()
        if self.otp == hashed_otp and self.otp_created_at:
            now = timezone.now()
            if now < self.otp_created_at + datetime.timedelta(minutes=1):  # OTP is valid for 1 minute
                return True
        return False


class MeetingBooking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Reference to the user who scheduled the meeting
    meeting_date = models.DateField(null=True, blank=True)  # Date of the meeting
    meeting_time = models.TimeField(null=True, blank=True)  # Time of the meeting
    venue = models.CharField(max_length=50, default='online')  # Venue, default is 'online'
    mandatory_attendees = models.TextField(null=True, blank=True)  # List of mandatory attendees
    optional_attendees = models.TextField(blank=True, null=True)  # List of optional attendees
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set at creation
    updated_at = models.DateTimeField(auto_now=True)  # Automatically updated on modification

    def __str__(self):
        return f"Meeting {self.booking_id} - {self.meeting_date} at {self.meeting_time}"


class UserSession(models.Model):
    session_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.session_id} for User {self.user_id}"