from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .api_views import AnalyzeAPIView, AnalysisListAPIView, CurrentUserView, DatasetDetailAPIView, DatasetListCreateAPIView, InsightsAPIView, LogoutAPIView, RegisterAPIView
from .views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/register/", RegisterAPIView.as_view(), name="api_auth_register"),
    path("auth/login/", TokenObtainPairView.as_view(permission_classes=[AllowAny]), name="api_auth_login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(permission_classes=[AllowAny]), name="api_token_refresh"),
    path("auth/logout/", LogoutAPIView.as_view(), name="api_auth_logout"),
    path("auth/me/", CurrentUserView.as_view(), name="api_current_user"),
    path("datasets/", DatasetListCreateAPIView.as_view(), name="api_datasets"),
    path("datasets/<int:pk>/", DatasetDetailAPIView.as_view(), name="api_dataset_detail"),
    path("analyze/", AnalyzeAPIView.as_view(), name="api_analyze"),
    path("insights/", InsightsAPIView.as_view(), name="api_insights"),
    path("analyses/", AnalysisListAPIView.as_view(), name="api_analyses"),
]
