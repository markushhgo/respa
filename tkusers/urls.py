"""URLs module"""
from django.urls import path
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from . import views


app_name = 'tkusers'

urlpatterns = [
    path('logout/', views.LogoutView.as_view(), name='auth_logout'),
    path('logout/complete/', views.LogoutCompleteView.as_view(), name='auth_logout_complete'),
    path('login/', views.LoginView.as_view(), name='auth_login'),
]

if not settings.RESPA_ADMIN_LOGOUT_REDIRECT_URL:
    raise ImproperlyConfigured("You must configure RESPA_ADMIN_LOGOUT_REDIRECT_URL to use tkusers views.")
