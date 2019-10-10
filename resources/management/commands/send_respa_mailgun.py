from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives


class Command(BaseCommand):
    help = 'Send test email through Django default backend'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send test email to.')
        parser.add_argument('subject', type=str, help='Email subject of the test email.')
        parser.add_argument('content', type=str, help='Email content of the test email.')

    def handle(self, *args, **options):
        assert settings.EMAIL_BACKEND == 'anymail.backends.mailgun.EmailBackend'
        assert settings.RESPA_MAILS_FROM_ADDRESS is not None
        assert settings.ANYMAIL['MAILGUN_API_KEY'] is not None
        assert settings.ANYMAIL['MAILGUN_SENDER_DOMAIN'] is not None
        assert settings.ANYMAIL['MAILGUN_API_URL'] is not None

        _from = (settings.RESPA_MAILS_FROM_ADDRESS)

        text_content = options['content'].strip()
        msg = EmailMultiAlternatives(options['subject'].strip(), text_content, _from, [options['email'].strip()])
        print('[%s] (%s) :: Sending email -=> (%s) "%s": %s' % (settings.ANYMAIL['MAILGUN_SENDER_DOMAIN'], _from, options['email'].strip(), options['subject'].strip(), text_content))
        """msg.send()"""
