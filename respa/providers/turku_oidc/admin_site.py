from django.conf import settings
import django.contrib.admin.apps as django_apps
from django.urls import reverse
import helusers.admin_site as hel_apps


PROVIDERS = (
    ('respa.providers.turku_oidc', 'turku_oidc_login'),
)

class AdminSite(hel_apps.AdminSite):
    login_template  = 'admin/tku_login.html'

    def __init__(self, *args, **kwargs):
        super(AdminSite, self).__init__(*args, **kwargs)

    def each_context(self, request):
        ret = super(AdminSite, self).each_context(request)
        ret['site_type'] = getattr(settings, 'SITE_TYPE', 'dev')
        ret['redirect_path'] = request.GET.get('next', None)
        provider_installed = False
        for provider, login_view in PROVIDERS:
            if provider not in settings.INSTALLED_APPS:
                continue
            provider_installed = True
            login_url = reverse(login_view)
            break
        logout_url = None

        ret['turku_provider_installed'] = provider_installed
        if provider_installed:
            ret['turku_login_url'] = login_url
            ret['turku_logout_url'] = logout_url

        ret['grappelli_installed'] = 'grappelli' in settings.INSTALLED_APPS
        if ret['grappelli_installed']:
            ret['grappelli_admin_title'] = self.site_header
            ret['base_site_template'] = 'admin/base_site_grappelli.html'
        else:
            ret['base_site_template'] = 'admin/base_site_default.html'

        ret['password_login_disabled'] = getattr(settings, 'HELUSERS_PASSWORD_LOGIN_DISABLED', False)

        return ret


class AdminConfig(django_apps.AdminConfig):
    default_site = 'respa.providers.turku_oidc.admin_site.AdminSite'
