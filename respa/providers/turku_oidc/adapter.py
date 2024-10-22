from helusers.adapter import DefaultSocialAccountAdapter
from helusers.user_utils import update_user as _update_user
from helusers.utils import username_to_uuid
from django.utils import timezone
from users.models import User, LoginMethod

def update_user(user, payload, oidc=False):
    amr = payload.pop('amr', None)
    if amr:
        user.amr, _ = LoginMethod.objects.get_or_create(id=amr)
    user.last_login = timezone.now()
    user.save()
    return _update_user(user, payload, oidc)

class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Update user based on token information."""
        user = sociallogin.user

        # If the user hasn't been saved yet, it will be updated
        # later on in the sign-up flow.
        if not user.pk:
            try:
                user = User.objects.get(uuid=username_to_uuid(user.username))
                sociallogin.connect(request, user)                  # We have to connect the user if we want to login from django || respa admin using tunnistamo
            except User.DoesNotExist:
                return
        data = sociallogin.account.extra_data
        oidc = sociallogin.account.provider == 'turku_oidc'
        update_user(user, data, oidc)
    

    def save_user(self, request, sociallogin, form=None):
        u = sociallogin.user
        u.uuid = username_to_uuid(u.username) # Set the correct assumed uuid
        u.set_unusable_password()
        sociallogin.save(request)

        data = sociallogin.account.extra_data
        oidc = sociallogin.account.provider == 'turku_oidc'
        update_user(u, data, oidc)
        return u