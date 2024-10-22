import datetime
import os
import re
import pytz
from collections import OrderedDict
from decimal import Decimal


import arrow
import django.db.models as dbm
from django.db.models import Q
from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from six import BytesIO
from django.utils.text import format_lazy
from django.utils.translation import pgettext_lazy, gettext_lazy as _
from django.contrib.postgres.fields import DateTimeRangeField
from .gistindex import GistIndex
from image_cropping import ImageRatioField
from PIL import Image
from guardian.shortcuts import get_objects_for_user, get_users_with_perms
from guardian.core import ObjectPermissionChecker


from taggit.managers import TaggableManager
from taggit.models import CommonGenericTaggedItemBase, TaggedItemBase

from ..auth import (
    is_authenticated_user, is_general_admin,
    is_underage, is_overage
)
from ..errors import InvalidImage
from ..fields import (
    EquipmentField,
    TranslatedCharField, TranslatedTextField,
    MultiEmailField
)
from .base import (
    AutoIdentifiedModel, NameIdentifiedModel,
    ModifiableModel, ValidatedIdentifier
)
from .utils import create_datetime_days_from_now, generate_id, get_translated, get_translated_name, humanize_duration
from .equipment import Equipment
from .resource_field import UniversalFormFieldType
from .unit import Unit
from .availability import get_opening_hours
from .permissions import RESOURCE_GROUP_PERMISSIONS, UNIT_ROLE_PERMISSIONS
from ..enums import UnitAuthorizationLevel, UnitGroupAuthorizationLevel

import logging


logger = logging.getLogger()


def generate_access_code(access_code_type):
    if access_code_type == Resource.ACCESS_CODE_TYPE_NONE:
        return ''
    elif access_code_type == Resource.ACCESS_CODE_TYPE_PIN4:
        return get_random_string(4, '0123456789')
    elif access_code_type == Resource.ACCESS_CODE_TYPE_PIN6:
        return get_random_string(6, '0123456789')
    else:
        raise NotImplementedError('Don\'t know how to generate an access code of type "%s"' % access_code_type)


def validate_access_code(access_code, access_code_type):
    if access_code_type == Resource.ACCESS_CODE_TYPE_NONE:
        return
    elif access_code_type == Resource.ACCESS_CODE_TYPE_PIN4:
        if not re.match('^[0-9]{4}$', access_code):
            raise ValidationError(dict(access_code=_('Invalid value')))
    elif access_code_type == Resource.ACCESS_CODE_TYPE_PIN6:
        if not re.match('^[0-9]{6}$', access_code):
            raise ValidationError(dict(access_code=_('Invalid value')))
    else:
        raise NotImplementedError('Don\'t know how to validate an access code of type "%s"' % access_code_type)

    return access_code


def determine_hours_time_range(begin, end, tz):
    if begin is None:
        begin = tz.localize(datetime.datetime.now()).date()
    if end is None:
        end = begin

    midnight = datetime.time(0, 0)
    begin = tz.localize(datetime.datetime.combine(begin, midnight))
    end = tz.localize(datetime.datetime.combine(end, midnight))
    end += datetime.timedelta(days=1)

    return begin, end


class ResourceTag(AutoIdentifiedModel):
    label = models.CharField(verbose_name=_('Tag label'), max_length=255)
    resource = models.ForeignKey('Resource', on_delete=models.CASCADE, related_name='resource_tags')


    def __str__(self):
        return '<%s: %s>' % (self.resource.name, self.label)


class ResourceType(ModifiableModel, AutoIdentifiedModel):
    MAIN_TYPES = (
        ('space', _('Space')),
        ('person', _('Person')),
        ('item', _('Item'))
    )
    id = models.CharField(primary_key=True, max_length=100)
    main_type = models.CharField(verbose_name=_('Main type'), max_length=20, choices=MAIN_TYPES)
    name = models.CharField(verbose_name=_('Name'), max_length=200)

    class Meta:
        verbose_name = _("resource type")
        verbose_name_plural = _("resource types")
        ordering = ('name',)

    def __str__(self):
        return "%s (%s)" % (get_translated(self, 'name'), self.id)


class Purpose(ModifiableModel, NameIdentifiedModel):
    id = models.CharField(primary_key=True, max_length=100)
    parent = models.ForeignKey('Purpose', verbose_name=_('Parent'), null=True, blank=True, related_name="children",
                               on_delete=models.SET_NULL)
    name = models.CharField(verbose_name=_('Name'), max_length=100)
    public = models.BooleanField(default=True, verbose_name=_('Public'))
    image = models.FileField(upload_to='purpose_images', validators=[FileExtensionValidator(['svg'])],
                                null=True, blank=True)

    class Meta:
        verbose_name = _("purpose")
        verbose_name_plural = _("purposes")
        ordering = ('name',)

    def __str__(self):
        return "%s (%s)" % (get_translated(self, 'name'), self.id)


class TermsOfUse(ModifiableModel, AutoIdentifiedModel):
    TERMS_TYPE_PAYMENT = 'payment_terms'
    TERMS_TYPE_GENERIC = 'generic_terms'

    TERMS_TYPES = (
        (TERMS_TYPE_PAYMENT, _('Payment terms')),
        (TERMS_TYPE_GENERIC, _('Generic terms'))
    )

    id = models.CharField(primary_key=True, max_length=100)
    name = models.CharField(verbose_name=_('Name'), max_length=200)
    text = models.TextField(verbose_name=_('Text'))
    terms_type = models.CharField(blank=False, verbose_name=_('Terms type'), max_length=40, choices=TERMS_TYPES, default=TERMS_TYPE_GENERIC)

    class Meta:
        verbose_name = pgettext_lazy('singular', 'terms of use')
        verbose_name_plural = pgettext_lazy('plural', 'terms of use')

    def __str__(self):
        return get_translated_name(self)


class ResourceQuerySet(models.QuerySet):
    def visible_for(self, user):
        if is_general_admin(user):
            return self
        is_in_managed_units = Q(unit__in=Unit.objects.managed_by(user))
        is_public = Q(_public=True)
        return self.filter(is_in_managed_units | is_public)

    def modifiable_by(self, user):
        if not is_authenticated_user(user):
            return self.none()

        if is_general_admin(user):
            return self

        units = Unit.objects.managed_by(user)
        return self.filter(unit__in=units)

    def with_perm(self, perm, user):
        units = get_objects_for_user(user, 'unit:%s' % perm, klass=Unit,
                                     with_superuser=False)
        resource_groups = get_objects_for_user(user, 'group:%s' % perm, klass=ResourceGroup,
                                               with_superuser=False)

        allowed_roles = UNIT_ROLE_PERMISSIONS.get(perm)
        units_where_role = Unit.objects.by_roles(user, allowed_roles)

        return self.filter(Q(unit__in=list(units) + list(units_where_role)) | Q(groups__in=resource_groups)).distinct()

    def external(self):
        return self.filter(is_external=True)

    def delete(self, *args, **kwargs):
        hard_delete = kwargs.pop('hard_delete', False)
        if hard_delete:
            return super().delete(*args, **kwargs)
        self.update(
            soft_deleted=True,
            _public=False,
            reservable=False
        )
        for publish_date in self.get_publish_dates():
            publish_date.delete()

    def restore(self):
        self.update(soft_deleted=False)

    def _refresh_publish_date_states(self):
        """Set resource public / reservable field according to publish_date value"""
        try:
            for resource in self:
                if resource.publish_date:
                    resource.publish_date._update_states()
        except:
            pass
        return self

    def get_publish_dates(self) -> list:
        return [resource.publish_date
                for resource in self
                if resource.publish_date]

class CleanResourceID(CommonGenericTaggedItemBase, TaggedItemBase):
    object_id = models.CharField(max_length=100, verbose_name=_('Object id'), db_index=True)


class ResourceManager(models.Manager):
    def get_queryset(self, **kwargs):
        if getattr(self, '_include_soft_deleted', False):
            setattr(self, '_include_soft_deleted', False)
            return super().get_queryset() \
                    ._refresh_publish_date_states()
        return super().get_queryset().exclude(soft_deleted=True) \
            ._refresh_publish_date_states()

    @property
    def with_soft_deleted(self):
        setattr(self, '_include_soft_deleted', True)
        return self


class Resource(ModifiableModel, AutoIdentifiedModel, ValidatedIdentifier):
    AUTHENTICATION_TYPES = (
        ('unauthenticated', _('Unauthenticated')),
        ('none', _('None')),
        ('weak', _('Weak')),
        ('strong', _('Strong'))
    )
    ACCESS_CODE_TYPE_NONE = 'none'
    ACCESS_CODE_TYPE_PIN4 = 'pin4'
    ACCESS_CODE_TYPE_PIN6 = 'pin6'
    ACCESS_CODE_TYPES = (
        (ACCESS_CODE_TYPE_NONE, _('None')),
        (ACCESS_CODE_TYPE_PIN4, _('4-digit PIN code')),
        (ACCESS_CODE_TYPE_PIN6, _('6-digit PIN code')),
    )

    PRICE_TYPE_HOURLY = 'hourly'
    PRICE_TYPE_DAILY = 'daily'
    PRICE_TYPE_WEEKLY = 'weekly'
    PRICE_TYPE_FIXED = 'fixed'
    PRICE_TYPE_CHOICES = (
        (PRICE_TYPE_HOURLY, _('Hourly')),
        (PRICE_TYPE_DAILY, _('Daily')),
        (PRICE_TYPE_WEEKLY, _('Weekly')),
        (PRICE_TYPE_FIXED, _('Fixed')),
    )
    id = models.CharField(primary_key=True, max_length=100)
    _public = models.BooleanField(default=True, verbose_name=_('Public'))

    unit = models.ForeignKey('Unit', verbose_name=_('Unit'), db_index=True, null=True, blank=True,
                             related_name="resources", on_delete=models.PROTECT)
    type = models.ForeignKey(ResourceType, verbose_name=_('Resource type'), db_index=True,
                             on_delete=models.PROTECT)
    purposes = models.ManyToManyField(Purpose, verbose_name=_('Purposes'))
    name = TranslatedCharField(verbose_name=_('Name'), max_length=200)
    description = TranslatedTextField(verbose_name=_('Description'), null=True, blank=True)

    tags = TaggableManager(through=CleanResourceID, blank=True)

    min_age = models.PositiveIntegerField(verbose_name=_('Age restriction (min)'), null=True, blank=True, default=0)
    max_age = models.PositiveIntegerField(verbose_name=_('Age restriction (max)'), null=True, blank=True, default=0)
    need_manual_confirmation = models.BooleanField(verbose_name=_('Need manual confirmation'), default=False)

    resource_staff_emails = MultiEmailField(verbose_name=_('E-mail addresses for client correspondence'), null=True, blank=True)

    authentication = models.CharField(blank=False, verbose_name=_('Authentication'),
                                      max_length=20, choices=AUTHENTICATION_TYPES)
    people_capacity = models.PositiveIntegerField(verbose_name=_('People capacity'), null=True, blank=True)
    area = models.PositiveIntegerField(verbose_name=_('Area (m2)'), null=True, blank=True)

    # if not set, location is inherited from unit
    location = models.PointField(verbose_name=_('Location'), null=True, blank=True, srid=settings.DEFAULT_SRID)

    min_period = models.DurationField(verbose_name=_('Minimum reservation time'),
                                      default=datetime.timedelta(minutes=30))
    max_period = models.DurationField(verbose_name=_('Maximum reservation time'), null=True, blank=True)

    cooldown = models.DurationField(verbose_name=_('Reservation cooldown'), null=True, blank=True, default=datetime.timedelta(minutes=0))

    slot_size = models.DurationField(verbose_name=_('Slot size for reservation time'), null=True, blank=True,
                                     default=datetime.timedelta(minutes=30), help_text=_('Note! If there are any products with per_period pricing that are attached to this resource'
                                     ', make sure that slot_size value is the same size as the products price_period value.'))

    equipment = EquipmentField(Equipment, through='ResourceEquipment', verbose_name=_('Equipment'))
    universal_field = models.ManyToManyField(UniversalFormFieldType, through='ResourceUniversalField', verbose_name=_('Universal fields'))
    max_reservations_per_user = models.PositiveIntegerField(verbose_name=_('Maximum number of active reservations per user'),
                                                            null=True, blank=True)
    reservable = models.BooleanField(verbose_name=_('Reservable'), default=False)
    reservation_info = TranslatedTextField(verbose_name=_('Reservation info'), null=True, blank=True)
    responsible_contact_info = TranslatedTextField(verbose_name=_('Responsible contact info'), blank=True)
    generic_terms = models.ForeignKey(TermsOfUse, verbose_name=_('Generic terms'), null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='resources_where_generic_terms')
    payment_terms = models.ForeignKey(TermsOfUse, verbose_name=_('Payment terms'), null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='resources_where_payment_terms')
    specific_terms = TranslatedTextField(verbose_name=_('Specific terms'), blank=True)
    reservation_requested_notification_extra = TranslatedTextField(verbose_name=_(
        'Extra content to "reservation requested" notification'), blank=True)
    reservation_confirmed_notification_extra = TranslatedTextField(verbose_name=_(
        'Extra content to "reservation confirmed" notification'), blank=True)
    reservation_additional_information = TranslatedTextField(verbose_name=_('Reservation additional information'), blank=True)


    min_price = models.DecimalField(verbose_name=_('Min price'), max_digits=8, decimal_places=2,
                                             blank=True, null=True, validators=[MinValueValidator(Decimal('0.00'))])
    max_price = models.DecimalField(verbose_name=_('Max price'), max_digits=8, decimal_places=2,
                                             blank=True, null=True, validators=[MinValueValidator(Decimal('0.00'))])

    price_type = models.CharField(
        max_length=32, verbose_name=_('price type'), choices=PRICE_TYPE_CHOICES, default=PRICE_TYPE_HOURLY
    )
    cash_payments_allowed = models.BooleanField(verbose_name=_('Cash payments allowed'), default=False,
        help_text=_('Allows cash payment option for paid reservations.'
            ' Can only be set when resource needs manual confirmation.')
    )
    payment_requested_waiting_time = models.PositiveIntegerField(
        verbose_name=_('Preliminary reservation payment waiting time'),
        help_text=_('Amount of hours before confirmed preliminary reservations with payments expire.'
            ' Value 0 means this setting is not in use.'),
        default=0, blank=True)

    access_code_type = models.CharField(verbose_name=_('Access code type'), max_length=20, choices=ACCESS_CODE_TYPES,
                                        default=ACCESS_CODE_TYPE_NONE)
    # Access codes can be generated either by the general Respa code or
    # the Kulkunen app. Kulkunen will set the `generate_access_codes`
    # attribute by itself if special access code considerations are
    # needed.
    generate_access_codes = models.BooleanField(
        verbose_name=_('Generate access codes'), default=True, editable=False,
        help_text=_('Should access codes generated by the general system')
    )
    reservable_by_all_staff = models.BooleanField(
        verbose_name=_('Resource is reservable by all staff users'),
        default=False,
        help_text=_('All staff users can create reservations on behalf of customers')
    )
    send_sms_notification = models.BooleanField(
        verbose_name=_('Send reservation SMS'),
        default=False,
        help_text=_('SMS will be sent to reserver in addition to email notifications. '
                    'Reservation requires phone number field to be set.')
    )
    reservable_max_days_in_advance = models.PositiveSmallIntegerField(verbose_name=_('Reservable max. days in advance'),
                                                                      null=True, blank=True)
    reservable_min_days_in_advance = models.PositiveSmallIntegerField(verbose_name=_('Reservable min. days in advance'),
                                                                      null=True, blank=True)
    reservation_metadata_set = models.ForeignKey(
        'resources.ReservationMetadataSet', verbose_name=_('Reservation metadata set'),
        null=True, blank=True, on_delete=models.SET_NULL
    )
    reservation_home_municipality_set = models.ForeignKey(
        'resources.ReservationHomeMunicipalitySet', verbose_name=_('Reservation home municipality set'),
        null=True, blank=True, on_delete=models.SET_NULL, related_name='home_municipality_included_set'
    )
    reservation_feedback_url = models.URLField(
        verbose_name=_('Reservation feedback URL'),
        help_text=_('A link to an external feedback system'),
        blank=True
    )

    overnight_reservations = models.BooleanField(verbose_name=_('Overnight reservations'),
                                                                default=False, blank=False,
                                                                help_text=_('Allow overnight reservations for this resource'))
    overnight_start_time = models.TimeField(verbose_name=_('Overnight start time'), null=True, blank=True)
    overnight_end_time = models.TimeField(verbose_name=_('Overnight end time'), null=True, blank=True)

    external_reservation_url = models.URLField(
        verbose_name=_('External reservation URL'),
        help_text=_('A link to an external reservation system if this resource is managed elsewhere'),
        null=True, blank=True)

    resource_email = models.EmailField(verbose_name='Email for Outlook', null=True, blank=True)
    configuration = models.ForeignKey('respa_outlook.RespaOutlookConfiguration', verbose_name=_('Outlook configuration'),
        null=True, blank=True, on_delete=models.SET_NULL, related_name='Configuration')

    timmi_resource = models.BooleanField(verbose_name=_('Is Timmi resource?'), default=False, blank=True, help_text=_('Is this resource part of Timmi integration?'))
    timmi_room_id = models.PositiveIntegerField(verbose_name=_('Timmi ID'), null=True, blank=True, help_text=_('This field will attempt to auto-fill if room id isn\'t provided.'))

    is_external = models.BooleanField(verbose_name=_('Externally managed resource'), default=False, blank=True)

    soft_deleted = models.BooleanField(verbose_name=_('Soft deleted resource'), default=False, blank=True)

    objects = ResourceManager.from_queryset(ResourceQuerySet)()

    class Meta:
        verbose_name = _("resource")
        verbose_name_plural = _("resources")
        ordering = ('unit', 'name',)

    def __str__(self):
        return "%s (%s)/%s" % (get_translated(self, 'name'), self.id, self.unit)

    def save(self, *args, **kwargs):
        if getattr(self, '_clean_func_lock', False):
            return
        return super().save(*args, **kwargs)

    @property
    def public(self):
        if self.publish_date:
            return self.publish_date.public
        return self._public

    @public.setter
    def public(self, value):
        if not isinstance(value, bool):
            raise TypeError(f"Invalid type: {type(value)} passed to {str(self.__class__.__name__)}.public")

        self._public = value
        if self.pk:
            self.save()

    @cached_property
    def main_image(self):
        resource_image = next(
            (image for image in self.images.all() if image.type == 'main'),
            None)

        return resource_image.image if resource_image else None

    def get_disabled_fields(self):
        """
        Check if Resource or Unit has disabled fields set,
        Resource takes priority
        """
        disabled_fields = []
        if self.pk:
            disabled_fields = getattr(self.disabled_fields_set.first(), 'disabled_fields', []) \
                or self.unit.get_disabled_fields()
        return disabled_fields

    def validate_reservation_period(self, reservation, user, data=None):
        """
        Check that given reservation if valid for given user.

        Reservation may be provided as Reservation or as a data dict.
        When providing the data dict from a serializer, reservation
        argument must be present to indicate the reservation being edited,
        or None if we are creating a new reservation.
        If the reservation is not valid raises a ValidationError.

        Staff members have no restrictions at least for now.

        Normal users cannot make multi day reservations or reservations
        outside opening hours.

        :type reservation: Reservation
        :type user: User
        :type data: dict[str, Object]
        """

        # no restrictions for staff
        if self.is_admin(user):
            return

        tz = self.unit.get_tz()
        # check if data from serializer is present:
        if data:
            begin = data['begin']
            end = data['end']
        else:
            # if data is not provided, the reservation object has the desired data:
            begin = reservation.begin
            end = reservation.end

        if begin.tzinfo:
            begin = begin.astimezone(tz)
        else:
            begin = tz.localize(begin)
        if end.tzinfo:
            end = end.astimezone(tz)
        else:
            end = tz.localize(end)

        # allow end to be at midnight and bypass check by moving end seconds back by one
        # to reservation day 23:59:59
        end_time = end.time()
        if end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0:
            end = end - datetime.timedelta(seconds=1)

        is_multiday_reservation = begin.date() != end.date()

        if is_multiday_reservation and not self.overnight_reservations:
            raise ValidationError(_("You cannot make a multiday reservation"))
        
        if self.overnight_reservations:
            if not user.is_superuser and not self.is_manager(user) and (begin.time() != self.overnight_start_time or end.time() != self.overnight_end_time):
                raise ValidationError(_("Reservation start and end must match the given overnight reservation start and end values"))

        if not self.can_ignore_opening_hours(user):
            opening_hours = self.get_opening_hours(begin.date(), end.date())
            days = opening_hours.get(begin.date(), None)
            if not is_multiday_reservation and (days is None or not any(day['opens'] and begin >= day['opens'] and end <= day['closes'] for day in days)):
                raise ValidationError(_("You must start and end the reservation during opening hours"))

        if not self.can_ignore_max_period(user) and (self.max_period and (end - begin) > self.max_period):
            raise ValidationError(_("The maximum reservation length is %(max_period)s") %
                                  {'max_period': humanize_duration(self.max_period)})

    def validate_max_reservations_per_user(self, user):
        """
        Check maximum number of active reservations per user per resource.
        If the user has too many reservations raises ValidationError.

        Staff members have no reservation limits.

        :type user: User
        """
        if self.can_ignore_max_reservations_per_user(user):
            return

        max_count = self.max_reservations_per_user
        if max_count is not None:
            reservation_count = self.reservations.filter(user=user).active().count()
            if reservation_count >= max_count:
                raise ValidationError(_("Maximum number of active reservations for this resource exceeded."))

    def check_reservation_collision(self, begin, end, reservation):
        overlapping = self.reservations.filter(end__gt=begin, begin__lt=end).active()
        if reservation:
            overlapping = overlapping.exclude(pk=reservation.pk)
        return overlapping.exists()

    def check_cooldown_collision(self, begin, end, reservation) -> bool:
        from .reservation import Reservation
        cooldown_start = begin - self.cooldown
        cooldown_end = end + self.cooldown
        query = (
            Q(begin__gt=cooldown_start, begin__lt=cooldown_end) |
            Q(end__gt=cooldown_start, end__lt=cooldown_end) |
            Q(begin__lt=cooldown_start, end__gt=begin) |
            Q(begin__lt=end, end__gt=cooldown_end)
        )

        query &= ~Q(type=Reservation.TYPE_BLOCKED)

        if reservation:
            query &= ~Q(pk=reservation.pk)

        cooldown_collisions = self.reservations.filter(query).active()
        return cooldown_collisions.exists()

    def get_available_hours(self, start=None, end=None, duration=None, reservation=None, during_closing=False):
        """
        Returns hours that the resource is not reserved for a given date range

        If include_closed=True, will also return hours when the resource is closed, if it is not reserved.
        This is so that admins can book resources during closing hours. Returns
        the available hours as a list of dicts. The optional reservation argument
        is for disregarding a given reservation during checking, if we wish to
        move an existing reservation. The optional duration argument specifies
        minimum length for periods to be returned.

        :rtype: list[dict[str, datetime.datetime]]
        :type start: datetime.datetime
        :type end: datetime.datetime
        :type duration: datetime.timedelta
        :type reservation: Reservation
        :type during_closing: bool
        """
        today = arrow.get(timezone.now())
        if start is None:
            start = today.floor('day').naive
        if end is None:
            end = today.replace(days=+1).floor('day').naive
        if not start.tzinfo and not end.tzinfo:
            """
            Only try to localize naive dates
            """
            tz = timezone.get_current_timezone()
            start = tz.localize(start)
            end = tz.localize(end)

        if not during_closing:
            """
            Check open hours only
            """
            open_hours = self.get_opening_hours(start, end)
            hours_list = []
            for date, open_during_date in open_hours.items():
                for period in open_during_date:
                    if period['opens']:
                        # if the start or end straddle opening hours
                        opens = period['opens'] if period['opens'] > start else start
                        closes = period['closes'] if period['closes'] < end else end
                        # include_closed to prevent recursion, opening hours need not be rechecked
                        hours_list.extend(self.get_available_hours(start=opens,
                                                                   end=closes,
                                                                   duration=duration,
                                                                   reservation=reservation,
                                                                   during_closing=True))
            return hours_list

        reservations = self.reservations.filter(
            end__gte=start, begin__lte=end).order_by('begin')
        hours_list = [({'starts': start})]
        first_checked = False
        for res in reservations:
            # skip the reservation that is being edited
            if res == reservation:
                continue
            # check if the reservation spans the beginning
            if not first_checked:
                first_checked = True
                if res.begin < start:
                    if res.end > end:
                        return []
                    hours_list[0]['starts'] = res.end
                    # proceed to the next reservation
                    continue
            if duration:
                if res.begin - hours_list[-1]['starts'] < duration:
                    # the free period is too short, discard this period
                    hours_list[-1]['starts'] = res.end
                    continue
            hours_list[-1]['ends'] = timezone.localtime(res.begin)
            # check if the reservation spans the end
            if res.end > end:
                return hours_list
            hours_list.append({'starts': timezone.localtime(res.end)})
        # after the last reservation, we must check if the remaining free period is too short
        if duration:
            if end - hours_list[-1]['starts'] < duration:
                hours_list.pop()
                return hours_list
        # otherwise add the remaining free period
        hours_list[-1]['ends'] = end
        return hours_list

    def get_opening_hours(self, begin=None, end=None, opening_hours_cache=None):
        """
        :rtype : dict[str, datetime.datetime]
        :type begin: datetime.date
        :type end: datetime.date
        """
        tz = pytz.timezone(self.unit.time_zone)
        begin, end = determine_hours_time_range(begin, end, tz)

        if opening_hours_cache is None:
            hours_objs = self.opening_hours.filter(open_between__overlap=(begin, end, '[)'))
        else:
            hours_objs = opening_hours_cache

        opening_hours = dict()
        for h in hours_objs:
            opens = h.open_between.lower.astimezone(tz)
            closes = h.open_between.upper.astimezone(tz)
            date = opens.date()
            hours_item = OrderedDict(opens=opens, closes=closes)
            date_item = opening_hours.setdefault(date, [])
            date_item.append(hours_item)

        # Set the dates when the resource is closed.
        date = begin.date()
        end = end.date()
        while date < end:
            if date not in opening_hours:
                opening_hours[date] = [OrderedDict(opens=None, closes=None)]
            date += datetime.timedelta(days=1)

        return opening_hours

    def update_opening_hours(self):
        hours = self.opening_hours.order_by('open_between')
        existing_hours = {}
        for h in hours:
            assert h.open_between.lower not in existing_hours
            existing_hours[h.open_between.lower] = h.open_between.upper

        unit_periods = list(self.unit.periods.all())
        resource_periods = list(self.periods.all())

        # Periods set for the resource always carry a higher priority. If
        # nothing is defined for the resource for a given day, use the
        # periods configured for the unit.
        for period in unit_periods:
            period.priority = 0
        for period in resource_periods:
            period.priority = 1

        earliest_date = None
        latest_date = None
        all_periods = unit_periods + resource_periods
        for period in all_periods:
            if earliest_date is None or period.start < earliest_date:
                earliest_date = period.start
            if latest_date is None or period.end > latest_date:
                latest_date = period.end

        # Assume we delete everything, but remove items from the delete
        # list if the hours are identical.
        to_delete = existing_hours
        to_add = {}
        if all_periods:
            hours = get_opening_hours(self.unit.time_zone, all_periods,
                                      earliest_date, latest_date)
            for hours_items in hours.values():
                for h in hours_items:
                    if not h['opens'] or not h['closes']:
                        continue
                    if h['opens'] in to_delete and h['closes'] == to_delete[h['opens']]:
                            del to_delete[h['opens']]
                            continue
                    to_add[h['opens']] = h['closes']

        if to_delete:
            ret = ResourceDailyOpeningHours.objects.filter(
                open_between__in=[(opens, closes, '[)') for opens, closes in to_delete.items()],
                resource=self
            ).delete()
            assert ret[0] == len(to_delete)

        add_objs = [
            ResourceDailyOpeningHours(resource=self, open_between=(opens, closes, '[)'))
            for opens, closes in to_add.items()
        ]
        if add_objs:
            ResourceDailyOpeningHours.objects.bulk_create(add_objs)

    def is_admin(self, user):
        """
        Check if the given user is an administrator of this resource.

        :type user: users.models.User
        :rtype: bool
        """
        # UserFilterBackend and ReservationFilterSet in resources.api.reservation assume the same behaviour,
        # so if this is changed those need to be changed as well.
        if not self.unit:
            return is_general_admin(user)
        return self.unit.is_admin(user)

    def is_manager(self, user):
        """
        Check if the given user is a manager of this resource.

        :type user: users.models.User
        :rtype: bool
        """
        if not self.unit:
            return False
        return self.unit.is_manager(user)

    def is_viewer(self, user):
        """
        Check if the given user is a viewer of this resource.

        :type user: users.models.User
        :rtype: bool
        """
        if not self.unit:
            return False
        return self.unit.is_viewer(user)

    def _has_perm(self, user, perm, allow_admin=True):
        if not is_authenticated_user(user):
            return False

        if (self.is_admin(user) and allow_admin) or user.is_superuser:
            return True

        if self.min_age and is_underage(user, self.min_age):
            return False

        if self.max_age and is_overage(user, self.max_age):
            return False

        if self.unit.is_manager(user) or self.unit.is_admin(user):
            return True

        return self._has_role_perm(user, perm) or self._has_explicit_perm(user, perm, allow_admin)

    def _has_explicit_perm(self, user, perm, allow_admin=True):
        if hasattr(self, '_permission_checker'):
            checker = self._permission_checker
        else:
            checker = ObjectPermissionChecker(user)

        # Permissions can be given per-unit
        if checker.has_perm('unit:%s' % perm, self.unit):
            return True
        # ... or through Resource Groups
        resource_group_perms = [checker.has_perm('group:%s' % perm, rg) for rg in self.groups.all()]
        return any(resource_group_perms)

    def _has_role_perm(self, user, perm):
        allowed_roles = UNIT_ROLE_PERMISSIONS.get(perm)
        is_allowed = False

        if (UnitAuthorizationLevel.admin in allowed_roles
            or UnitGroupAuthorizationLevel.admin in allowed_roles) and not is_allowed:
            is_allowed = self.is_admin(user)

        if UnitAuthorizationLevel.manager in allowed_roles and not is_allowed:
            is_allowed = self.is_manager(user)

        if UnitAuthorizationLevel.viewer in allowed_roles and not is_allowed:
            is_allowed = self.is_viewer(user)

        return is_allowed

    def get_users_with_perm(self, perm):
        users = {u for u in get_users_with_perms(self.unit) if u.has_perm('unit:%s' % perm, self.unit)}
        for rg in self.groups.all():
            users |= {u for u in get_users_with_perms(rg) if u.has_perm('group:%s' % perm, rg)}
        return users

    def can_make_reservations(self, user):
        if self.min_age and is_underage(user, self.min_age):
            return False
        if self.max_age and is_overage(user, self.max_age):
            return False

        return self.reservable or self._has_perm(user, 'can_make_reservations')

    def can_modify_reservations(self, user):
        return self._has_perm(user, 'can_modify_reservations')

    def can_comment_reservations(self, user):
        return self._has_perm(user, 'can_comment_reservations')

    def can_ignore_opening_hours(self, user):
        return self._has_perm(user, 'can_ignore_opening_hours')

    def can_view_reservation_extra_fields(self, user):
        return self._has_perm(user, 'can_view_reservation_extra_fields')

    def can_view_reservation_user(self, user):
        return self._has_perm(user, 'can_view_reservation_user')

    def can_access_reservation_comments(self, user):
        return self._has_perm(user, 'can_access_reservation_comments')

    def can_view_reservation_catering_orders(self, user):
        return self._has_perm(user, 'can_view_reservation_catering_orders')

    def can_modify_reservation_catering_orders(self, user):
        return self._has_perm(user, 'can_modify_reservation_catering_orders')

    def can_view_reservation_product_orders(self, user):
        return self._has_perm(user, 'can_view_reservation_product_orders', allow_admin=False)

    def can_modify_paid_reservations(self, user):
        return self._has_perm(user, 'can_modify_paid_reservations', allow_admin=False)

    def can_approve_reservations(self, user):
        return self._has_perm(user, 'can_approve_reservation', allow_admin=False)

    def can_view_reservation_access_code(self, user):
        return self._has_perm(user, 'can_view_reservation_access_code')

    def can_bypass_payment(self, user):
        return self._has_perm(user, 'can_bypass_payment')

    def can_create_staff_event(self, user):
        return self._has_perm(user, 'can_create_staff_event')

    def can_create_special_type_reservation(self, user):
        return self._has_perm(user, 'can_create_special_type_reservation')

    def can_bypass_manual_confirmation(self, user):
        return self._has_perm(user, 'can_bypass_manual_confirmation')

    def can_create_reservations_for_other_users(self, user):
        user_is_generic_staff = bool(user and user.is_staff)
        return self._has_perm(user, 'can_create_reservations_for_other_users') or (user_is_generic_staff and self.reservable_by_all_staff)

    def can_create_overlapping_reservations(self, user):
        return self._has_perm(user, 'can_create_overlapping_reservations')

    def can_ignore_max_reservations_per_user(self, user):
        return self._has_perm(user, 'can_ignore_max_reservations_per_user')

    def can_ignore_max_period(self, user):
        return self._has_perm(user, 'can_ignore_max_period')

    def is_access_code_enabled(self):
        return self.access_code_type != Resource.ACCESS_CODE_TYPE_NONE

    def get_reservable_max_days_in_advance(self):
        return self.reservable_max_days_in_advance or self.unit.reservable_max_days_in_advance

    def get_reservable_before(self):
        return create_datetime_days_from_now(self.get_reservable_max_days_in_advance())

    def get_reservable_min_days_in_advance(self):
        return self.reservable_min_days_in_advance or self.unit.reservable_min_days_in_advance

    def get_reservable_after(self):
        return create_datetime_days_from_now(self.get_reservable_min_days_in_advance())

    def has_rent(self):
        return self.products.current().rents().exists()

    def get_supported_reservation_extra_field_names(self, cache=None):
        if not self.reservation_metadata_set_id:
            return []
        if cache:
            metadata_set = cache[self.reservation_metadata_set_id]
        else:
            metadata_set = self.reservation_metadata_set
        return [x.field_name for x in metadata_set.supported_fields.all()]

    def get_required_reservation_extra_field_names(self, cache=None):
        if not self.reservation_metadata_set:
            return []
        if cache:
            metadata_set = cache[self.reservation_metadata_set_id]
        else:
            metadata_set = self.reservation_metadata_set
        return [x.field_name for x in metadata_set.required_fields.all()]

    def get_included_home_municipality_names(self, cache=None):
        if not self.reservation_home_municipality_set_id:
            return []
        if cache:
            home_municipality_set = cache[self.reservation_home_municipality_set_id]
        else:
            home_municipality_set = self.reservation_home_municipality_set
        # get home municipalities with translations [{id: {fi, en, sv}}, ...]
        included_municipalities = home_municipality_set.included_municipalities.all()
        result_municipalities = []

        for municipality in included_municipalities:
            result_municipalities.append({
                'id': municipality.id,
                "name": {
                        'fi': municipality.name_fi,
                        'en': municipality.name_en,
                        'sv': municipality.name_sv
                }
            })
        return result_municipalities

    def clean(self):
        from resources.timmi import TimmiManager
        setattr(self, '_clean_func_lock', True)
        if self.cooldown is None:
            self.cooldown = datetime.timedelta(0)
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValidationError(
                {'min_price': _('This value cannot be greater than max price')}
            )
        if self.min_period % self.slot_size != datetime.timedelta(0):
            raise ValidationError({'min_period': _('This value must be a multiple of slot_size')})

        if self.cooldown % self.slot_size != datetime.timedelta(0):
            raise ValidationError({'cooldown': _('This value must be a multiple of slot_size')})

        if self.authentication == 'unauthenticated':
            if self.min_age and self.min_age > 0:
                raise ValidationError(
                    {'min_age': format_lazy(
                        '{}'*2,
                        *[_('This value cannot be set to more than zero if resource authentication is: '),
                            _('Unauthenticated')]
                        )}
                )
            if self.max_age and self.max_age > 0:
                raise ValidationError(
                     {'max_age': format_lazy(
                        '{}'*2,
                        *[_('This value cannot be set to more than zero if resource authentication is: '),
                            _('Unauthenticated')]
                        )}
                )
            if self.max_reservations_per_user and self.max_reservations_per_user > 0:
                raise ValidationError(
                     {'max_reservations_per_user': format_lazy(
                        '{}'*2,
                        *[_('This value cannot be set to more than zero if resource authentication is: '),
                            _('Unauthenticated')]
                        )}
                )
            if self.is_access_code_enabled():
                raise ValidationError(
                    {'access_code_type': format_lazy(
                        '{}'*2,
                        *[_('This cannot be enabled if resource authentication is: '),
                            _('Unauthenticated')]
                        )}
                )

        if self.cash_payments_allowed and not self.need_manual_confirmation:
            raise ValidationError({
                'cash_payments_allowed': _('Cash payments are only allowed when reservations need manual confirmation')
            })

        if self.overnight_reservations:
            if self.overnight_end_time > self.overnight_start_time:
                raise ValidationError({
                    'overnight_end_time': _('Overnight reservation end time cannot be greater than start time')
                })

        if self.timmi_resource and not self.timmi_room_id:
            TimmiManager().get_room_part_id(self)

        if self.id:
            self.validate_id()

        setattr(self, '_clean_func_lock', False)

    def get_products(self):
        return self.products.current()

    def has_products(self):
        return self.products.current().exists()

    def has_outlook_link(self):
        return getattr(self, 'outlookcalendarlink', False)

    @property
    def publish_date(self):
        return getattr(self, '_publish_date', None)

    def delete(self, *args, **kwargs):
        self.soft_deleted = True
        self.public = False
        self.reservable = False
        return self.save()

    def restore(self):
        if not self.soft_deleted:
            logger.debug(_('Resource isn\'t soft deleted, no action required'))
            return
        self.soft_deleted = False
        return self.save()

class ResourcePublishDate(models.Model):
    begin = models.DateTimeField(
        verbose_name=_('Begin time'),
        help_text=_('Resource will be public after this date'),
        null=True, blank=True
    )
    end = models.DateTimeField(
        verbose_name=_('End time'),
        help_text=_('Resource will be hidden after this date'),
        null=True, blank=True
    )
    reservable = models.BooleanField(
        verbose_name=_('Reservable'),
        help_text=_('Allow reservations'),
        default=False
    )
    resource = models.OneToOneField(
        Resource, verbose_name=_('Resource'),
        db_index=True, related_name='_publish_date',
        on_delete=models.CASCADE
    )


    def clean(self):
        if not self.begin and not self.end:
            raise ValidationError({
                'begin': _('This field must be set if {field} is empty').format(field=_('End time')).capitalize(),
                'end': _('This field must be set if {field} is empty').format(field=_('Begin time')).capitalize(),
            })
        elif self.begin and self.end:
            if self.begin > self.end:
                raise ValidationError({
                    'begin': _('Begin time must be before end time')
                })

        if self.begin:
            self.begin = self.begin.replace(microsecond=0, second=0)
        if self.end:
            if timezone.now() > self.end:
                raise ValidationError({
                    'end': _('End time cannot be in the past')
                })
            self.end = self.end.replace(microsecond=0, second=0)


    def _get_public(self):
        if self.begin and self.end:
            is_public = self.begin < timezone.now() < self.end
        elif self.begin and not self.end:
            is_public = timezone.now() > self.begin
        elif self.end and not self.begin:
            is_public = timezone.now() < self.end
        else:
            return self.resource._public
        return is_public

    @property
    def public(self):
        self._update_states()
        return self._get_public()


    def _update_states(self):
        self.resource.public = self._get_public()
        self.resource.reservable = self.reservable
        self.resource.save()

    def __str__(self):
        return f'{self.resource.name}: {self.format_begin_end()}'

    def format_begin_end(self):
        begin = timezone.localtime(self.begin) if self.begin else ''
        end = timezone.localtime(self.end) if self.end else ''
        fmt = f'{begin}{" - " if begin and end else ""}{end}'
        return f'{self._get_fmt_title()} {fmt}'

    def _get_fmt_title(self):
        if self.begin and self.end:
            return _('Public between')
        elif self.begin and not self.end:
            if timezone.now() > self.begin:
                return _('Published since')
            else:
                return _('Public after')
        elif self.end and not self.begin:
            if timezone.now() < self.end:
                return _('Public until')
            else:
                return _('Hidden since')
        else:
            return super(ResourcePublishDate, self).__str__()

    def _get_fmt_icon(self):
        if self.resource.public:
            return 'shape-success'
        else:
            return 'shape-warning'

    def format_html(self):
        from django.utils.safestring import mark_safe
        begin = timezone.localtime(self.begin).strftime('%d.%m.%y %H:%M') \
            if self.begin else ''
        end = timezone.localtime(self.end).strftime('%d.%m.%y %H:%M') \
            if self.end else ''
        return mark_safe(
            f"""
            <div style="display: flex; flex-direction: row; align-items: center;">
                <div style="display: flex; flex-direction: column;">
                    <h6><i class="glyphicon glyphicon-time" style="margin-right: 5px;"></i>{self._get_fmt_title()}</h6>
                    {f"<span>{begin}{' - ' if begin and end else ''}</span>" if begin else ""}
                    {f"<span>{end}</span>" if end else ""}
                </div>
            </div>
            """
        )

class ResourceImage(ModifiableModel):
    TYPES = (
        ('main', _('Main photo')),
        ('ground_plan', _('Ground plan')),
        ('map', _('Map')),
        ('other', _('Other')),
    )
    resource = models.ForeignKey('Resource', verbose_name=_('Resource'), db_index=True,
                                 related_name='images', on_delete=models.CASCADE)
    type = models.CharField(max_length=20, verbose_name=_('Type'), choices=TYPES)
    caption = models.CharField(max_length=100, verbose_name=_('Caption'), null=True, blank=True)
    # FIXME: name images based on resource, type, and sort_order
    image = models.ImageField(verbose_name=_('Image'), upload_to='resource_images')
    image_format = models.CharField(max_length=10)
    cropping = ImageRatioField('image', '800x800', verbose_name=_('Cropping'))
    sort_order = models.PositiveSmallIntegerField(verbose_name=_('Sort order'))
    stamp = models.CharField(max_length=255, null=True, blank=True, unique=True)

    def save(self, *args, **kwargs):
        self._process_image()
        if self.sort_order is None:
            other_images = self.resource.images.order_by('-sort_order')
            if not other_images:
                self.sort_order = 0
            else:
                self.sort_order = other_images[0].sort_order + 1
        if self.type == "main":
            other_main_images = self.resource.images.filter(type="main")
            if other_main_images.exists():
                # Demote other main images to "other".
                # The other solution would be to raise an error, but that would
                # lead to a more awkward API experience (having to first patch other
                # images for the resource, then fix the last one).
                other_main_images.update(type="other")
        if not self.stamp:
            stamp = generate_id()
            while ResourceImage.objects.filter(stamp=stamp).exists():
                stamp = generate_id()
            self.stamp = stamp
        return super(ResourceImage, self).save(*args, **kwargs)

    def full_clean(self, exclude=(), validate_unique=True):
        if "image" not in exclude:
            self._process_image()
        return super(ResourceImage, self).full_clean(exclude, validate_unique)

    def _get_io_stream(self, img, **kwargs):
        _bytes_io = BytesIO()
        img.save(_bytes_io, format=self.image_format, **kwargs)
        return _bytes_io

    def _get_content_file(self, img, **kwargs):
        return ContentFile(
            self._get_io_stream(img, **kwargs).getvalue(),
            name=os.path.splitext(self.image.name)[0] + ".%s" % self.image_format.lower()
        )

    def _process_image(self):
        """
        Preprocess the uploaded image file, if required.

        This may transcode the image to a JPEG or PNG if it's not either to begin with.

        :raises InvalidImage: Exception raised if the uploaded file is not valid.
        """
        if not self.image:  # No image set - we can't do this right now
            return
        save_kwargs = {}
        with Image.open(self.image) as img:
            if img.size > (1920, 1080):
                img.thumbnail((1920, 1080), Image.LANCZOS)
                self.cropping = None
                setattr(self, '_processing_required', True)
            elif img.size < (128, 128):
                raise InvalidImage("Image %s not valid (Image is too small)" % self.image)

            if img.format not in ("JPEG", "PNG"):  # Needs transcoding.
                if self.type in ("map", "ground_plan"):
                    target_format = "PNG"
                else:
                    target_format = "JPEG"
                    save_kwargs = {"quality": 75, "progressive": True}
                self.image_format = target_format
                setattr(self, '_processing_required', True)
            else:  # All good -- keep the file as-is.
                self.image_format = img.format

            if getattr(self, '_processing_required', False):
                self.image = self._get_content_file(img, **save_kwargs)

    def get_full_url(self):
        base_url = getattr(settings, 'RESPA_IMAGE_BASE_URL', None)
        if not base_url:
            return None
        return base_url.rstrip('/') + reverse('resource-image-view', args=[str(self.id)])

    def __str__(self):
        return "%s image for %s" % (self.get_type_display(), str(self.resource))

    class Meta:
        verbose_name = _('resource image')
        verbose_name_plural = _('resource images')
        unique_together = (('resource', 'sort_order'),)


class ResourceEquipment(ModifiableModel):
    """This model represents equipment instances in resources.

    Contains data and description related to a specific equipment instance.
    Data field can be used to set custom attributes for more flexible and fast filtering.
    """
    resource = models.ForeignKey(Resource, related_name='resource_equipment', on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment, related_name='resource_equipment', on_delete=models.CASCADE)
    data = models.JSONField(verbose_name=_('Data'), null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = pgettext_lazy('singular', 'resource equipment')
        verbose_name_plural = pgettext_lazy('plural', 'resource equipment')

    def __str__(self):
        return "%s / %s" % (self.equipment, self.resource)


class ResourceUniversalField(ModifiableModel):
    name = models.CharField(verbose_name=_('Name'), max_length=100)
    resource = models.ForeignKey(Resource, verbose_name=_('Resource'), related_name='resource_universal_field', on_delete=models.CASCADE)
    field_type = models.ForeignKey(
        UniversalFormFieldType,
        verbose_name=_('Type'),
        related_name='resource_universal_field',
        on_delete=models.CASCADE
        )
    data = models.JSONField(verbose_name=_('Data'), null=True, blank=True)
    label = models.CharField(verbose_name=_('Heading'), max_length=100)
    description = models.TextField(verbose_name=_('Description'), blank=True)

    class Meta:
        verbose_name = _('resource universal form field')
        verbose_name_plural = _('resource universal form fields')

    @property
    def options(self):
        return ResourceUniversalFormOption.objects.filter(resource_universal_field=self)

    def __str__(self):
        return "%s / %s / %s" % (self.name, self.field_type, self.resource)

class ResourceUniversalFormOption(ModifiableModel):
    name = models.CharField(verbose_name=_('Name'), max_length=100)
    resource_universal_field = models.ForeignKey('ResourceUniversalField', verbose_name=_('Type'), on_delete=models.CASCADE)
    resource = models.ForeignKey('Resource', related_name='resource_universal_form_option', on_delete=models.CASCADE)
    text = models.TextField(verbose_name=_('Text'), blank=True)
    sort_order = models.PositiveSmallIntegerField(verbose_name=_('Sort order'))

    class Meta:
        verbose_name = _('resource universal form option')
        verbose_name_plural = _('resource universal form options')
        ordering = ('sort_order', )

    def __str__(self):
        if hasattr(self, 'resource_universal_field'):
            return "%s / %s" % (self.name, self.resource_universal_field)
        return "%s / ?" % (self.name)


class ResourceGroup(ModifiableModel):
    identifier = models.CharField(verbose_name=_('Identifier'), max_length=100)
    name = models.CharField(verbose_name=_('Name'), max_length=200)
    resources = models.ManyToManyField(Resource, verbose_name=_('Resources'), related_name='groups', blank=True)

    class Meta:
        verbose_name = _('Resource group')
        verbose_name_plural = _('Resource groups')
        permissions = RESOURCE_GROUP_PERMISSIONS
        ordering = ('name',)

    def __str__(self):
        return self.name


class ResourceDailyOpeningHours(models.Model):
    """
    Calculated automatically for each day the resource is open
    """
    resource = models.ForeignKey(
        Resource, related_name='opening_hours', on_delete=models.CASCADE, db_index=True
    )
    open_between = DateTimeRangeField()

    def clean(self):
        super().clean()
        if self.objects.filter(resource=self.resource, open_between__overlaps=self.open_between):
            raise ValidationError(_("Overlapping opening hours"))

    class Meta:
        unique_together = [
            ('resource', 'open_between')
        ]
        indexes = [
            GistIndex(fields=['open_between'])
        ]

    def __str__(self):
        if isinstance(self.open_between, tuple):
            lower = self.open_between[0]
            upper = self.open_between[1]
        else:
            lower = self.open_between.lower
            upper = self.open_between.upper
        return "%s: %s -> %s" % (self.resource, lower, upper)
