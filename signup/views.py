from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from signup.serializers import (
    SignupSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


class SignupView(views.APIView):
    def post(self, request):
        """
        POST request to create a new user
        Input format:
        {
            "username": "string",
            "email": "string",
            "password": "string"
        }
        """
        # Check if the email already exists
        if User.objects.filter(email=request.data.get("email")).exists():
            return Response(
                {'error': "A user with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Proceed with serializer validation if email is unique
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User created successfully"},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SigninView(views.APIView):
    def post(self, request):
        """
        POST request to sign in a user
        Input format:
        {
            "username": "string",
            "password": "string"
        }
        """
        username = request.data.get("username")
        password = request.data.get("password")

        # Validate input
        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                    },
                    "message": "Login successful",
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class ForgotPasswordView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Initiates the password reset process by sending an email with a reset token.
        """
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            try:
                user = User.objects.get(email=email)
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))  # Encode user ID

                # Generate the reset link
                reset_link = f"http://localhost:3000/reset-password/{uid}/{token}/"

                # Send the reset email
                send_mail(
                    "Password Reset Request",
                    f"Click the link to reset your password: {reset_link}",
                    "no-reply@example.com",
                    [email],
                    fail_silently=False,
                )

                return Response(
                    {"detail": "Password reset link sent to your email."},
                    status=status.HTTP_200_OK,
                )
            except User.DoesNotExist:
                return Response(
                    {"detail": "User with this email does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Resets the password using the token provided in the password reset link.
        """
        # Retrieve the new password from request body
        token = kwargs.get("token")
        uidb64 = kwargs.get("uidb64")
        serializer = ResetPasswordSerializer(data=request.data)

        # Make sure the serializer is valid
        if serializer.is_valid():
            new_password = serializer.validated_data["new_password"]

            try:
                # Decode the UID to get the user
                user_id = urlsafe_base64_decode(uidb64).decode()
                print(user_id)
                user = User.objects.get(pk=user_id)
                print(user.username)

                # Validate the token
                if default_token_generator.check_token(user, token):
                    user.set_password(new_password)
                    user.save()
                    return Response(
                        {"detail": "Password successfully reset."},
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"detail": "Invalid or expired token."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
                )

        # If serializer is not valid, return the errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
