from .settings import *


RESPA_CATERINGS_ENABLED = True
RESPA_COMMENTS_ENABLED = True
RESPA_PAYMENTS_ENABLED = True
# Bambora Payform provider settings
RESPA_PAYMENTS_PROVIDER_CLASS = 'payments.providers.BamboraPayformProvider'
RESPA_PAYMENTS_BAMBORA_API_URL = 'https://real-bambora-api-url/api'
RESPA_PAYMENTS_BAMBORA_API_KEY = 'dummy-key'
RESPA_PAYMENTS_BAMBORA_API_SECRET = 'dummy-secret'
RESPA_PAYMENTS_BAMBORA_PAYMENT_METHODS = ['dummy-bank']
DJANGO_ADMIN_LOGOUT_REDIRECT_URL='https://hel.fi'
RESPA_ADMIN_LOGOUT_REDIRECT_URL='https://hel.fi'
# API token auth endpoint
MACHINE_TO_MACHINE_AUTH_ENABLED=1
STRONG_AUTH_CLAIMS=('very_strong_auth', )
HELUSERS_PROVIDER = 'helusers.providers.helsinki'
RESPA_PAYMENTS_BAMBORA_TOKEN_VALID_DAYS = 3
RESPA_PAYMENTS_PAYMENT_REQUESTED_WAITING_TIME = 24
SIMPLE_JWT['AUDIENCE'] = 'https://dummy-aud.respa.turku.fi'
SIMPLE_JWT['SIGNING_KEY'] = 'very-secret-signing-key'