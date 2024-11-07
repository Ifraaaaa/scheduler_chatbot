from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.mail import send_mail
from scheduler_app.models import User, UserSession
from scheduler_app.serializers import OTPRequestSerializer, OTPVerifySerializer
from scheduler_project import settings
from datetime import timedelta
import datetime
import jwt
from decouple import config

success_otp = "OTP sent successfully"
error_verify = "Email is not verified"
error_register = "Email not registered"
error_invalid = "Invalid OTP or OTP expired"

@api_view(['POST'])
def request_otp(request):
    serializer = OTPRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            if user.status:
                otp = user.generate_otp()  # Generate and get the raw OTP
                subject = "Your OTP for Login"
                message = f"Hi {user.full_name},\n\nYour OTP for login is: {otp}"
                send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
                return Response({"success": True, "message": success_otp}, status=status.HTTP_200_OK)
            else:
                return Response({"success": False, "message": error_verify}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"success": False, "message": error_register}, status=status.HTTP_200_OK)
    return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def verify_otp(request):
    serializer = OTPVerifySerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        try:
            user = User.objects.get(email=email)
            if user.is_otp_valid(otp):
                response_data = {
                    "id": user.id,
                    "full_name": user.full_name,
                    "email": user.email
                }
                expiry_time = datetime.datetime.utcnow() + timedelta(hours=24)

                # Include expiration time in payload
                response_data['exp'] = expiry_time

                encoded = jwt.encode(response_data, config('mysecret'), algorithm='HS256')
                access_token = {
                    "access_token": encoded
                }

                # Create a new user session
                session = UserSession.objects.create(
                    user=user,
                    session_token=encoded,
                    expires_at=expiry_time
                )

                return Response({"success": True, "access_token": encoded}, status=status.HTTP_200_OK)
            else:
                return Response({"success": False, "message": error_invalid}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"success": False, "message": error_register}, status=status.HTTP_200_OK)
    return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
