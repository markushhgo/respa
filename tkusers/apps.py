from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin.apps import AdminConfig


class TkuUsersConfig(AppConfig):
    name = 'tkusers'
    verbose_name = _("Turku Users")


class TkuUsersAdminConfig(AdminConfig):
    default_site = 'tkusers.admin.AdminSite'
