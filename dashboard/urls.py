from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from .views import analyst_page, dashboard, datasets_page, insights_page, register, reports_page

urlpatterns = [
    path("login/", LoginView.as_view(
        template_name="auth/login.html",
        redirect_authenticated_user=True,
    ), name="login"),
    path("register/", register, name="register"),
    path("datasets/", datasets_page, name="datasets"),
    path("analyst/", analyst_page, name="analyst"),
    path("insights/", insights_page, name="insights"),
    path("reports/", reports_page, name="reports"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("", dashboard, name="dashboard"),
]
