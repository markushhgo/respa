import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from django.utils.formats import date_format
from jinja2 import StrictUndefined
from jinja2.exceptions import TemplateError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment
from parler.models import TranslatableModel, TranslatedFields
from parler.utils.context import switch_language
from resources.models.base import ModifiableModel

DEFAULT_LANG = settings.LANGUAGES[0][0]

logger = logging.getLogger('respa.notifications')


class NotificationType:
    RESERVATION_REQUESTED = 'reservation_requested'
    RESERVATION_REQUESTED_OFFICIAL = 'reservation_requested_official'
    RESERVATION_REQUESTED_BY_OFFICIAL = 'reservation_requested_official_by_official'

    RESERVATION_CANCELLED = 'reservation_cancelled'
    RESERVATION_CANCELLED_OFFICIAL = 'reservation_cancelled_official'
    RESERVATION_CANCELLED_BY_OFFICIAL = 'reservation_cancelled_by_official'

    RESERVATION_CREATED = 'reservation_created'
    RESERVATION_REMINDER = 'reservation_reminder'
    RESERVATION_CREATED_OFFICIAL = 'reservation_created_official'
    RESERVATION_CREATED_BY_OFFICIAL = 'reservation_created_by_official'

    RESERVATION_MODIFIED = 'reservation_modified'
    RESERVATION_MODIFIED_OFFICIAL = 'reservation_modified_official'
    RESERVATION_MODIFIED_BY_OFFICIAL = 'reservation_modified_by_official'

    RESERVATION_CONFIRMED = 'reservation_confirmed'
    RESERVATION_DENIED = 'reservation_denied'

    # If the access code is known at reservation time, this notification
    # type is used.
    RESERVATION_CREATED_WITH_ACCESS_CODE = 'reservation_created_with_access_code'
    RESERVATION_CREATED_WITH_ACCESS_CODE_OFFICIAL = 'reservation_created_with_access_code_official'
    RESERVATION_CREATED_WITH_ACCESS_CODE_BY_OFFICIAL = 'reservation_created_with_access_code_by_official'
    # In some cases, the access code is known only some time after the
    # reservation is made. A separate notification type is used so that
    # we don't confuse the user with "new reservation created"-style
    # messaging.
    RESERVATION_ACCESS_CODE_CREATED = 'reservation_access_code_created'
    RESERVATION_WAITING_FOR_PAYMENT = 'reservation_waiting_for_payment'
    CATERING_ORDER_CREATED = 'catering_order_created'
    CATERING_ORDER_MODIFIED = 'catering_order_modified'
    CATERING_ORDER_DELETED = 'catering_order_deleted'
    CATERING_ORDER_COMMENT_CREATED = 'catering_order_comment_created'

    RESERVATION_COMMENT_CREATED = 'reservation_comment_created'
    RESERVATION_COMMENT_CREATED_BY_OFFICIAL = 'reservation_comment_created_by_official'

    RESERVATION_BULK_CREATED = 'reservation_bulk_created'


class NotificationTemplateException(Exception):
    pass



class NotificationTemplate(TranslatableModel):
    NOTIFICATION_TYPE_CHOICES = (
        (NotificationType.RESERVATION_REQUESTED, _('Reservation requested')),
        (NotificationType.RESERVATION_REQUESTED_OFFICIAL, _('Reservation requested official')),
        (NotificationType.RESERVATION_REQUESTED_BY_OFFICIAL, _('Reservation requested by official')),

        (NotificationType.RESERVATION_CANCELLED, _('Reservation cancelled')),
        (NotificationType.RESERVATION_CANCELLED_OFFICIAL, _('Reservation cancelled official')),
        (NotificationType.RESERVATION_CANCELLED_BY_OFFICIAL, _('Reservation cancelled by official')),

        (NotificationType.RESERVATION_CREATED, _('Reservation created')),
        (NotificationType.RESERVATION_CREATED_OFFICIAL, _('Reservation created official')),
        (NotificationType.RESERVATION_CREATED_BY_OFFICIAL, _('Reservation created by official')),

        (NotificationType.RESERVATION_MODIFIED, _('Reservation modified')),
        (NotificationType.RESERVATION_MODIFIED_OFFICIAL, _('Reservation modified official')),
        (NotificationType.RESERVATION_MODIFIED_BY_OFFICIAL, _('Reservation modified by official')),

        (NotificationType.RESERVATION_CREATED_WITH_ACCESS_CODE, _('Reservation created with access code')),
        (NotificationType.RESERVATION_CREATED_WITH_ACCESS_CODE_OFFICIAL, _('Reservation created with access code official')),
        (NotificationType.RESERVATION_CREATED_WITH_ACCESS_CODE_BY_OFFICIAL, _('Reservation created with access code by official')),

        (NotificationType.RESERVATION_CONFIRMED, _('Reservation confirmed')),
        (NotificationType.RESERVATION_DENIED, _('Reservation denied')),
        (NotificationType.RESERVATION_ACCESS_CODE_CREATED, _('Access code was created for a reservation')),
        (NotificationType.RESERVATION_WAITING_FOR_PAYMENT, _('Reservation waiting for payment')),

        (NotificationType.CATERING_ORDER_CREATED, _('Catering order created')),
        (NotificationType.CATERING_ORDER_MODIFIED, _('Catering order modified')),
        (NotificationType.CATERING_ORDER_DELETED, _('Catering order deleted')),
        (NotificationType.RESERVATION_COMMENT_CREATED, _('Reservation comment created')),
        (NotificationType.CATERING_ORDER_COMMENT_CREATED, _('Catering order comment created')),

        (NotificationType.RESERVATION_BULK_CREATED, _('Reservation bulk created')),
        (NotificationType.RESERVATION_REMINDER, _('Reservation reminder')),
    )

    type = models.CharField(
        verbose_name=_('Type'), choices=NOTIFICATION_TYPE_CHOICES, max_length=100, db_index=True
    )
    name = models.CharField(
        verbose_name=_('Name'), max_length=100, default='default', help_text=_('Name that is used to help differentiate between two templates when listing all templates.')
    )

    is_default_template = models.BooleanField(
        verbose_name=_('Set this template as a default template.'), default=False, help_text=_('Use this template as a default template for this type.')
    )

    translations = TranslatedFields(
        short_message=models.TextField(
            verbose_name=_('Short message'), blank=True, help_text=_('Short notification text for e.g. SMS messages')
        ),
        subject=models.CharField(
            verbose_name=_('Subject'), max_length=200, help_text=_('Subject for email notifications')
        ),
        body=models.TextField(verbose_name=_('Body'), help_text=_('Text body for email notifications'), blank=True),
        html_body=models.TextField(
            verbose_name=_('HTML body'), help_text=_('HTML body for email notifications'), blank=True,
        )
    )

    class Meta:
        verbose_name = _('Notification template')
        verbose_name_plural = _('Notification templates')

    def __str__(self):
        for t in self.NOTIFICATION_TYPE_CHOICES:
            if t[0] == self.type:
                if self.name:
                    return str(t[1]) + ' ' + self.name
                else:
                    return str(t[1])
        return 'N/A'

    def render(self, context, language_code=DEFAULT_LANG):
        """
        Render this notification template with given context and language

        Returns a dict containing all content fields of the template. Example:

        {'short_message': 'foo', 'subject': 'bar', 'body': 'baz', 'html_body': '<b>foobar</b>'}

        """

        env = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        env.filters['reservation_time'] = reservation_time
        env.filters['format_datetime'] = format_datetime
        env.filters['format_datetime_tz'] = format_datetime_tz

        logger.debug('Rendering template for notification %s' % self.type)
        with switch_language(self, language_code):
            try:
                rendered_notification = {
                    attr: env.from_string(getattr(self, attr)).render(context)
                    for attr in ('short_message', 'subject', 'html_body')
                }
                if self.body:
                    rendered_notification['body'] = env.from_string(self.body).render(context)
                else:
                    # if text body is empty use html body without tags as text body
                    rendered_notification['body'] = strip_tags(rendered_notification['html_body'])
                return rendered_notification
            except TemplateError as e:
                raise NotificationTemplateException(e) from e

    def clean(self, **kwargs):
        super().clean()
        if self.is_default_template:
            if NotificationTemplate.objects.filter(id=self.id, type=self.type, is_default_template=True).exists():
                logger.info("Saving modified default template of type {}.".format(self.type))

            elif NotificationTemplate.objects.filter(type=self.type, is_default_template=True).exists():
                logger.info("Attempted to save a new default template. A default template of type {} already exists.".format(self.type))
                raise ValidationError({'is_default_template':_('Default template already exists')})

            elif NotificationTemplate.objects.filter(type=self.type, is_default_template=False).exists():
                logger.info("New default template of type {} was created.".format(self.type))

        self.validate_templates()

    def validate_templates(self):
        context = {}
        env = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        env.filters['reservation_time'] = reservation_time
        env.filters['format_datetime'] = format_datetime
        env.filters['format_datetime_tz'] = format_datetime_tz
        templates = ['short_message', 'body', 'html_body']
        for template in templates:
            try:
                env.from_string(getattr(self, template)).render(context)
            except UndefinedError as e:
                # context can have various variables that are hard to test without actual data
                # so we just skip validation for them
                continue
            except TemplateError as e:
                raise ValidationError({template: e})


def reservation_time(res):
    if isinstance(res, dict):
        return res['time_range']
    return res.format_time()


def format_datetime(dt):
    current_language = translation.get_language()
    if current_language == 'fi':
        # ma 1.1.2017 klo 12.00
        dt_format = r'D j.n.Y \k\l\o G.i'
    else:
        # default to English
        dt_format = r'D j/n/Y G:i'

    return date_format(dt, dt_format)


def format_datetime_tz(dt, tz):
    dt = dt.astimezone(tz)
    return format_datetime(dt)


def render_notification_template(notification_type, context, language_code=DEFAULT_LANG):
    try:
        template = NotificationTemplate.objects.get(type=notification_type)
    except NotificationTemplate.DoesNotExist as e:
        raise NotificationTemplateException(e) from e

    return template.render(context, language_code)

class NotificationTemplateGroup(ModifiableModel):
    identifier = models.CharField(verbose_name=_('Identifier'), max_length=100)
    name = models.CharField(verbose_name=_('Name'), max_length=200)
    templates = models.ManyToManyField(NotificationTemplate,
                                        verbose_name=_('Notification templates'),
                                        related_name='groups',
                                        blank=True,
                                        limit_choices_to={'is_default_template': False})

    class Meta:
        verbose_name = _('Notification template group')
        verbose_name_plural = _('Notification template groups')
        ordering = ('name',)

    def __str__(self):
        return self.name

