from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.mail import send_mail
from django.urls import reverse
from django.shortcuts import redirect
from scheduler_app.models import User
from scheduler_app.serializers import UserSerializer
from scheduler_project import settings

success_registration = "User registered successfully. Verification email sent."
success_verify = "Email id is successfully verified"
token_invalid = "Invalid token"


@api_view(['POST'])
def register(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        verification_url = request.build_absolute_uri(reverse('verify')) + f'?token={user.verification_token}'
        subject = "Verify your email"
        message = f"Hi {user.full_name},\n\nPlease verify your email by clicking on the link below:\n\n{verification_url}"
        send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
        return Response({"message": success_registration}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def verify_email(request):
    token = request.GET.get('token')
    try:
        user = User.objects.get(verification_token=token)
        user.status = True
        user.save()
        return Response({"message":success_verify}, status=status.HTTP_201_CREATED)
    except User.DoesNotExist:
        return Response({"error": token_invalid}, status=status.HTTP_400_BAD_REQUEST)