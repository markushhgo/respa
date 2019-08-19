from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns
from .provider import TurkuOIDCProvider

urlpatterns = default_urlpatterns(TurkuOIDCProvider)
