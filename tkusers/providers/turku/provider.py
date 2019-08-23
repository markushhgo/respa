from allauth.socialaccount import providers
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider

from tkusers.utils import uuid_to_username


class TurkuAccount(ProviderAccount):
    def get_profile_url(self):
        return self.account.extra_data.get('html_url')

    def get_avatar_url(self):
        return self.account.extra_data.get('avatar_url')

    def to_str(self):
        dflt = super(TurkuAccount, self).to_str()
        return self.account.extra_data.get('name', dflt)


class TurkuProvider(OAuth2Provider):
    id = 'turku'
    name = 'City of Turku employees'
    package = 'tkusers.providers.turku'
    account_class = TurkuAccount

    def extract_uid(self, data):
        return str(data['uuid'])

    def extract_common_fields(self, data):
        ret = data.copy()
        ret['username'] = uuid_to_username(data['uuid'])
        return ret

    def get_default_scope(self):
        return ['read']


providers.registry.register(TurkuProvider)
