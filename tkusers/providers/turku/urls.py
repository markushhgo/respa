from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns
from .provider import TurkuProvider

urlpatterns = default_urlpatterns(TurkuProvider)
