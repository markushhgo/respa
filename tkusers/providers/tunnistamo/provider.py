from allauth.socialaccount import providers
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider

from tkusers.user_utils import oidc_to_user_data
from tkusers.utils import uuid_to_username


class TurkuOIDCAccount(ProviderAccount):
    def get_profile_url(self):
        return self.account.extra_data.get('html_url')

    def get_avatar_url(self):
        return self.account.extra_data.get('avatar_url')

    def to_str(self):
        dflt = super(TurkuOIDCAccount, self).to_str()
        return self.account.extra_data.get('name', dflt)


class TurkuOIDCProvider(OAuth2Provider):
    id = 'tunnistamo'
    name = 'City of Turku employees (OIDC)'
    package = 'tkusers.providers.tunnistamo'
    account_class = TurkuOIDCAccount

    def extract_uid(self, data):
        return str(data['sub'])

    def extract_common_fields(self, data):
        ret = oidc_to_user_data(data)
        ret['username'] = uuid_to_username(data['sub'])
        return ret

    def get_default_scope(self):
        return ['openid profile email']


providers.registry.register(TurkuOIDCProvider)
