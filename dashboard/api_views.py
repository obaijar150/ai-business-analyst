from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from .dataset_processing import inspect_dataset
from .ai.providers.base import AnalysisProviderError
from .ai.service import analyze_dataset
from .insights import generate_insights
from .models import AnalysisRecord, Dataset
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already in use.")
        return value

    def validate_password(self, value):
        try:
            username = self.initial_data.get("username", "")
            validate_password(value, user=User(username=username))
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


class RegisterAPIView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LogoutAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        raw_refresh_token = request.data.get("refresh")
        if not raw_refresh_token:
            return Response(
                {"refresh": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh_token = RefreshToken(raw_refresh_token)
            if str(refresh_token.get("user_id")) != str(request.user.pk):
                return Response(
                    {"refresh": ["This token does not belong to the current user."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            refresh_token.blacklist()
        except TokenError:
            return Response(
                {"refresh": ["Invalid or expired refresh token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class DatasetUploadSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, allow_blank=False)
    file = serializers.FileField()

    def create(self, validated_data):
        upload = validated_data["file"]
        try:
            processed = inspect_dataset(upload)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"file": error.messages}) from error
        name = validated_data.get("name") or upload.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        return Dataset.objects.create(
            owner=self.context["request"].user,
            name=name,
            file=upload,
            **processed,
        )


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = (
            "id", "name", "file", "file_type", "row_count", "column_count",
            "columns", "statistics", "metadata", "created_at",
        )
        read_only_fields = fields


class DatasetListCreateAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication, SessionAuthentication)

    def get(self, request):
        datasets = Dataset.objects.filter(owner=request.user)
        return Response(DatasetSerializer(datasets, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = DatasetUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        dataset = serializer.save()
        return Response(
            DatasetSerializer(dataset, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DatasetDetailAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication, SessionAuthentication)

    def get_object(self, request, pk):
        return get_object_or_404(Dataset, pk=pk, owner=request.user)

    def get(self, request, pk):
        dataset = self.get_object(request, pk)
        return Response(DatasetSerializer(dataset, context={"request": request}).data)

    def delete(self, request, pk):
        self.get_object(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnalyzeSerializer(serializers.Serializer):
    dataset_id = serializers.IntegerField(min_value=1)
    question = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class AnalyzeAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication, SessionAuthentication)

    def post(self, request):
        serializer = AnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dataset = get_object_or_404(
            Dataset,
            pk=serializer.validated_data["dataset_id"],
            owner=request.user,
        )
        try:
            result = analyze_dataset(dataset, serializer.validated_data["question"])
        except AnalysisProviderError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        record = AnalysisRecord.objects.create(
            owner=request.user,
            dataset=dataset,
            question=result["question"],
            analysis=result["analysis"],
            result=result["result"],
            explanation=result["explanation"],
            evidence=result["evidence"],
        )
        result["analysis_id"] = record.pk
        return Response(result)


class InsightsAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication, SessionAuthentication)

    def get(self, request):
        dataset_id = request.query_params.get("dataset_id")
        if not dataset_id:
            return Response({"detail": "dataset_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        dataset = get_object_or_404(Dataset, pk=dataset_id, owner=request.user)
        try:
            return Response(generate_insights(dataset))
        except AnalysisProviderError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
