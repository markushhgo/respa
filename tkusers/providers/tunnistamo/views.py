import requests

from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter, OAuth2LoginView, OAuth2CallbackView
)
from .provider import TurkuOIDCProvider
from tkusers.settings import settings

class TurkuOIDCOAuth2Adapter(OAuth2Adapter):
    provider_id = TurkuOIDCProvider.id
    access_token_url = '%s/openid/token/' % getattr(settings, 'OIDC_AUTH')['ISSUER']
    authorize_url = '%s/openid/authorize/' % getattr(settings, 'OIDC_AUTH')['ISSUER']
    profile_url = '%s/openid/userinfo/' % getattr(settings, 'OIDC_AUTH')['ISSUER']

    def complete_login(self, request, app, token, **kwargs):
        headers = {'Authorization': 'Bearer {0}'.format(token.token)}
        resp = requests.get(self.profile_url, headers=headers)
        assert resp.status_code == 200
        extra_data = resp.json()
        return self.get_provider().sociallogin_from_response(request,
                                                             extra_data)


oauth2_login = OAuth2LoginView.adapter_view(TurkuOIDCOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(TurkuOIDCOAuth2Adapter)
