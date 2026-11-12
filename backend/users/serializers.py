from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        read_only_fields = ['id']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
class UserProfileSerializer(serializers.ModelSerializer):

 class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields
from rest_framework_simplejwt.tokens import RefreshToken


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs

    def save(self, **kwargs):
        token = RefreshToken(self.token)
        token.blacklist()
class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):

    username_field = User.EMAIL_FIELD

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        password = attrs.get("password")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password."}
            )

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.get_username(),
            password=password
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password."}
            )

        if not authenticated_user.is_active:
            raise serializers.ValidationError(
                {"detail": "User account is disabled."}
            )

        refresh = self.get_token(authenticated_user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }