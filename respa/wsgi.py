"""
WSGI config for respa project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

project_path = None
app_path = None


try:
    for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), 'r').read().split('\n'):
        if line.split('=')[0].strip() == 'RESPA_PROJECT_PATH':
            project_path = line.split('=')[1].replace('\'','').strip()       # TODO
        elif line.split('=')[0].strip() == 'RESPA_APP_PATH':
            app_path = line.split('=')[1].replace('\'','').strip()
except:
    pass #travis cli

if project_path and project_path not in sys.path:
    sys.path.append(project_path)

if app_path and app_path not in sys.path:
    sys.path.append(app_path)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "respa.settings")

application = get_wsgi_application()
