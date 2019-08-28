"""
WSGI config for respa project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

if sys.prefix not in sys.path:
    sys.path.append(sys.prefix)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "respa.settings")

application = get_wsgi_application()
