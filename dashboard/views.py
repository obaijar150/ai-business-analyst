from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.shortcuts import redirect, render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@login_required
def dashboard(request):
    return render(request, "dashboard/index.html")


@login_required
def datasets_page(request):
    return render(request, "dashboard/datasets.html")


@login_required
def analyst_page(request):
    setup_required = settings.AI_PROVIDER == "gemini" and not settings.GEMINI_API_KEY
    return render(request, "dashboard/analyst.html", {"gemini_setup_required": setup_required})


@login_required
def insights_page(request):
    return render(request, "dashboard/insights.html", {})


@login_required
def reports_page(request):
    return render(request, "dashboard/reports.html", {})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user)
        return redirect("dashboard")
    return render(request, "auth/register.html", {"form": form})


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})
