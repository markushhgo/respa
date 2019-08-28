"""
WSGI config for respa project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import sys
import environ

from django.core.wsgi import get_wsgi_application

if sys.prefix not in sys.path:
    sys.path.append(sys.prefix)
env = environ.Env(
    RESPA_PROJECT_PATH = (str, ''),
    RESPA_APP_PATH = (str, '')
)
environ.Env.read_env()

project_path = env('RESPA_PROJECT_PATH')
app_path = env('RESPA_APP_PATH')

if project_path and project_path not in sys.path:
    sys.path.append(project_path)

if app_path and app_path not in sys.path:
    sys.path.append(app_path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "respa.settings")

application = get_wsgi_application()
