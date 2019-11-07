from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .user_utils import update_user

class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        if not user.pk:
            return

        data = sociallogin.account.extra_data
        oidc = sociallogin.account.provider == 'tunnistamo'
        update_user(user, data, oidc)

    def populate_user(self, request, sociallogin, data):
        user = sociallogin.user
        exclude_fields = ['is_staff', 'password', 'is_supervisor', 'id']
        user_fields = [f.name for f in user._meta.fields if f not in exclude_fields]
        for field in user_fields:
            if field in data:
                setattr(user, field, data[field])
        return user

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        user.set_unusable_password()
        sociallogin.save(request)

        data = sociallogin.account.extra_data
        oidc = sociallogin.account.provider == 'tunnistamo'

        update_user(user, data, oidc)
        return user
