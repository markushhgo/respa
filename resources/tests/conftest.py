# -*- coding: utf-8 -*-
import pytest
import datetime
import base64
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from resources.enums import UnitAuthorizationLevel
from resources.models import Resource, ResourceType, Unit, Purpose, Day, Period, Reservation, ResourcePublishDate
from resources.models import Equipment, EquipmentAlias, ResourceEquipment, EquipmentCategory, TermsOfUse, ResourceGroup
from resources.models import AccessibilityValue, AccessibilityViewpoint, ResourceAccessibility, UnitAccessibility
from resources.models import ResourceUniversalFormOption, ResourceUniversalField, UniversalFormFieldType
from resources.models import ReservationMetadataSet, ReservationMetadataField
from users.models import LoginMethod
from munigeo.models import Municipality
from maintenance.models import MaintenanceMessage, MaintenanceMode
from .utils import get_test_image_data, get_test_image_payload

@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def staff_api_client(staff_user):
    api_client = APIClient()
    api_client.force_authenticate(user=staff_user)
    return api_client

@pytest.fixture
def unit_manager_api_client(unit_manager_user):
    api_client = APIClient()
    api_client.force_authenticate(user=unit_manager_user)
    return api_client

@pytest.fixture
def user_api_client(user):
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture(params=[None, 'user', 'staff_user'])
def all_user_types_api_client(request):
    api_client = APIClient()
    if request.param:
        api_client.force_authenticate(request.getfixturevalue(request.param))
    return api_client


@pytest.fixture
def api_rf():
    return APIRequestFactory()


@pytest.mark.django_db
@pytest.fixture
def space_resource_type():
    return ResourceType.objects.get_or_create(id="test_space", name="test_space", main_type="space")[0]


@pytest.mark.django_db
@pytest.fixture
def space_resource(space_resource_type) -> Resource:
    return Resource.objects.create(type=space_resource_type, authentication="none", name="resource")

@pytest.mark.django_db
@pytest.fixture
def test_unit() -> Unit:
    return Unit.objects.create(name="unit", time_zone='Europe/Helsinki')


@pytest.fixture
def test_unit2() -> Unit:
    return Unit.objects.create(name="unit 2", time_zone='Europe/Helsinki')


@pytest.fixture
def test_unit3() -> Unit:
    return Unit.objects.create(name="unit 3", time_zone='Europe/Helsinki')


@pytest.fixture
def test_unit4() -> Unit:
    return Unit.objects.create(
            name="unit 4",
            time_zone='Europe/Helsinki',
            disallow_overlapping_reservations=True
        )

@pytest.mark.django_db
@pytest.fixture
def test_unit_with_reminders_enabled() -> Unit:
    return Unit.objects.create(
        name="unit",
        time_zone='Europe/Helsinki',
        sms_reminder=True,
        sms_reminder_delay=24
    )

@pytest.fixture
def generic_terms():
    return TermsOfUse.objects.create(
        name_fi='testikäyttöehdot',
        name_en='test terms of use',
        text_fi='kaikki on kielletty',
        text_en='everything is forbidden',
    )


@pytest.fixture
def payment_terms():
    return TermsOfUse.objects.create(
        name_fi='testimaksuehdot',
        name_en='test terms of payment',
        text_fi='kaikki on maksullista',
        text_en='everything is chargeable',
        terms_type=TermsOfUse.TERMS_TYPE_PAYMENT
    )

@pytest.fixture
def metadataset_1():
    name_field = ReservationMetadataField.objects.get(field_name='reserver_name')
    email_field = ReservationMetadataField.objects.get(field_name='reserver_email_address')
    phone_field = ReservationMetadataField.objects.get(field_name='reserver_phone_number')
    metadata_set = ReservationMetadataSet.objects.create(
        name='test_metadataset_1',
        )
    metadata_set.supported_fields.set([name_field, email_field, phone_field])
    return metadata_set


@pytest.mark.django_db
@pytest.fixture
def resource_with_metadata(space_resource_type, metadataset_1, test_unit) -> Resource:
    return Resource.objects.create(
        type=space_resource_type,
        authentication="none",
        name="resource with metadata",
        reservation_metadata_set=metadataset_1,
        unit=test_unit,
        reservable=True,
    )


@pytest.mark.django_db
@pytest.fixture
def resource_in_unit(space_resource_type, test_unit, generic_terms, payment_terms) -> Resource:
    return Resource.objects.create(
        type=space_resource_type,
        authentication="none",
        name="resource in unit",
        unit=test_unit,
        max_reservations_per_user=1,
        max_period=datetime.timedelta(hours=2),
        reservable=True,
        generic_terms=generic_terms,
        payment_terms=payment_terms,
        specific_terms_fi='spesifiset käyttöehdot',
        specific_terms_en='specific terms of use',
        reservation_confirmed_notification_extra_en='this resource rocks'
    )


@pytest.mark.django_db
@pytest.fixture
def resource_in_unit2(space_resource_type, test_unit2) -> Resource:
    return Resource.objects.create(
        type=space_resource_type,
        authentication="none",
        name="resource in unit 2",
        unit=test_unit2,
        max_reservations_per_user=2,
        max_period=datetime.timedelta(hours=4),
        reservable=True,
    )


@pytest.mark.django_db
@pytest.fixture
def resource_in_unit3(space_resource_type, test_unit3) -> Resource:
    return Resource.objects.create(
        type=space_resource_type,
        authentication="none",
        name="resource in unit 3",
        unit=test_unit3,
        max_reservations_per_user=2,
        max_period=datetime.timedelta(hours=4),
        reservable=True,
    )


@pytest.mark.django_db
@pytest.fixture
def resource_in_unit4_1(space_resource_type, test_unit4) -> Resource:
    resource = Resource.objects.create(
        type=space_resource_type,
        authentication="none",
        name="resource in unit 4 first",
        unit=test_unit4,
        max_reservations_per_user=5,
        max_period=datetime.timedelta(hours=4),
        reservable=True,
    )
    p1 = Period.objects.create(start=datetime.date(2115, 1, 1),
                               end=datetime.date(2115, 12, 31),
                               resource=resource, name='regular hours')
    for weekday in range(0, 7):
        Day.objects.create(period=p1, weekday=weekday,
                           opens=datetime.time(8, 0),
                           closes=datetime.time(18, 0))
    resource.update_opening_hours()
    return resource


@pytest.mark.django_db
@pytest.fixture
def resource_in_unit4_2(space_resource_type, test_unit4) -> Resource:
    resource = Resource.objects.create(
        type=space_resource_type,
        authentication="none",
        name="resource in unit 4 second",
        unit=test_unit4,
        max_reservations_per_user=5,
        max_period=datetime.timedelta(hours=4),
        reservable=True,
    )
    p1 = Period.objects.create(start=datetime.date(2115, 1, 1),
                               end=datetime.date(2115, 12, 31),
                               resource=resource, name='regular hours')
    for weekday in range(0, 7):
        Day.objects.create(period=p1, weekday=weekday,
                           opens=datetime.time(8, 0),
                           closes=datetime.time(18, 0))
    resource.update_opening_hours()
    return resource


@pytest.mark.django_db
@pytest.fixture
def resource_with_opening_hours(resource_in_unit) -> Resource:
    p1 = Period.objects.create(start=datetime.date(2115, 1, 1),
                               end=datetime.date(2115, 12, 31),
                               resource=resource_in_unit, name='regular hours')
    for weekday in range(0, 7):
        Day.objects.create(period=p1, weekday=weekday,
                           opens=datetime.time(8, 0),
                           closes=datetime.time(18, 0))
    resource_in_unit.update_opening_hours()
    return resource_in_unit

@pytest.fixture
def resource_with_manual_confirmation(resource_with_opening_hours) -> Resource:
    resource_with_opening_hours.need_manual_confirmation = True
    resource_with_opening_hours.save()
    return resource_with_opening_hours

@pytest.mark.django_db
@pytest.fixture
def strong_resource(resource_with_opening_hours) -> Resource:
    resource_with_opening_hours.authentication = "strong"
    resource_with_opening_hours.save()
    return resource_with_opening_hours

@pytest.mark.django_db
@pytest.fixture
def resource_with_reservation_reminders(
    resource_with_opening_hours, 
    metadataset_1,
    test_unit_with_reminders_enabled) -> Resource:
    resource_with_opening_hours.unit = test_unit_with_reminders_enabled
    resource_with_opening_hours.reservation_metadata_set = metadataset_1
    resource_with_opening_hours.save()
    return resource_with_opening_hours

@pytest.mark.django_db
@pytest.fixture
def resource_with_cooldown(resource_with_opening_hours) -> Resource:
    resource_with_opening_hours.cooldown='04:00:00'
    resource_with_opening_hours.max_reservations_per_user = 10
    resource_with_opening_hours.save()
    return resource_with_opening_hours

@pytest.mark.django_db
@pytest.fixture
def resource_with_overnight_reservations(resource_in_unit4_1) -> Resource:
    resource_in_unit4_1.max_period = '48:00:00'
    resource_in_unit4_1.overnight_reservations = True
    resource_in_unit4_1.overnight_start_time = '08:00:00'
    resource_in_unit4_1.overnight_end_time = '16:00:00'
    resource_in_unit4_1.save()
    return resource_in_unit4_1

@pytest.mark.django_db
@pytest.fixture
def exceptional_period(resource_with_opening_hours):
    parent = resource_with_opening_hours.periods.first()
    period = Period.objects.create(start='2115-01-10', end='2115-01-12',
                                   resource=resource_with_opening_hours,
                                   name='exceptional hours',
                                   exceptional=True, parent=parent)

    date = period.start
    Day.objects.create(period=period, weekday=date.weekday(),
                       closed=True)
    date = date + datetime.timedelta(days=1)
    Day.objects.create(period=period, weekday=date.weekday(),
                       opens='12:00', closes='13:00')
    date = date + datetime.timedelta(days=1)
    Day.objects.create(period=period, weekday=date.weekday(),
                       closed=True)

    return period


@pytest.mark.django_db
@pytest.fixture
def equipment_category():
    return EquipmentCategory.objects.create(
        name='test equipment category'
    )


@pytest.mark.django_db
@pytest.fixture
def equipment(equipment_category):
    equipment = Equipment.objects.create(name='test equipment', category=equipment_category)
    return equipment


@pytest.mark.django_db
@pytest.fixture
def equipment_alias(equipment):
    equipment_alias = EquipmentAlias.objects.create(name='test equipment alias', language='fi', equipment=equipment)
    return equipment_alias


@pytest.mark.django_db
@pytest.fixture
def resource_equipment(resource_in_unit, equipment):
    data = {'test_key': 'test_value'}
    resource_equipment = ResourceEquipment.objects.create(
        equipment=equipment,
        resource=resource_in_unit,
        data=data,
        description='test resource equipment',
    )
    return resource_equipment

@pytest.mark.django_db
@pytest.fixture
def strong_auth_login_method():
    return LoginMethod.objects.create(id='very_strong_auth', name='Very Strong Auth')

@pytest.mark.django_db
@pytest.fixture
def weak_auth_login_method():
    return LoginMethod.objects.create(id='very_weak_auth', name='Very Weak Auth')
    

@pytest.mark.django_db
@pytest.fixture
def strong_user(strong_auth_login_method):
    user = get_user_model().objects.create(
        username='test_user_super_strong',
        first_name='Evert',
        last_name='Bäckström',
        email='cem@kaner.com',
        preferred_language='en',
        amr=strong_auth_login_method
    )
    return user

@pytest.mark.django_db
@pytest.fixture
def user():
    return get_user_model().objects.create(
        username='test_user',
        first_name='Cem',
        last_name='Kaner',
        email='cem@kaner.com',
        preferred_language='en'
    )


@pytest.mark.django_db
@pytest.fixture
def user2():
    return get_user_model().objects.create(
        username='test_user2',
        first_name='Brendan',
        last_name='Neutra',
        email='brendan@neutra.com'
    )


@pytest.mark.django_db
@pytest.fixture
def staff_user():
    return get_user_model().objects.create(
        username='test_staff_user',
        first_name='John',
        last_name='Staff',
        email='john@staff.com',
        is_staff=True,
        preferred_language='en'
    )

@pytest.mark.django_db
@pytest.fixture
def unit_admin_user(resource_in_unit):
    user = get_user_model().objects.create(
        username='test_admin_user',
        first_name='Inspector',
        last_name='Lestrade',
        email='lestrade@scotlandyard.co.uk',
        is_staff=True,
        preferred_language='en'
    )
    user.unit_authorizations.create(subject=resource_in_unit.unit, level=UnitAuthorizationLevel.admin)
    return user


@pytest.mark.django_db
@pytest.fixture
def unit_manager_user(resource_in_unit):
    user = get_user_model().objects.create(
        username='test_manager_user',
        first_name='Inspector',
        last_name='Lestrade',
        email='lestrade@scotlandyard.co.uk',
        is_staff=True,
        preferred_language='en'
    )
    user.unit_authorizations.create(subject=resource_in_unit.unit, level=UnitAuthorizationLevel.manager)
    return user


@pytest.mark.django_db
@pytest.fixture
def unit4_manager_user(resource_in_unit4_1):
    user = get_user_model().objects.create(
        username='test_manager_user',
        first_name='Inspector',
        last_name='Lestrade',
        email='lestrade@scotlandyard.co.uk',
        is_staff=True,
        preferred_language='en'
    )
    user.unit_authorizations.create(subject=resource_in_unit4_1.unit, level=UnitAuthorizationLevel.manager)
    return user


@pytest.mark.django_db
@pytest.fixture
def unit_viewer_user(resource_in_unit):
    user = get_user_model().objects.create(
        username='test_viewer_user',
        first_name='Inspector',
        last_name='Watson',
        email='watson@scotlandyard.co.uk',
        is_staff=True,
        preferred_language='en'
    )
    user.unit_authorizations.create(subject=resource_in_unit.unit, level=UnitAuthorizationLevel.viewer)
    return user

@pytest.mark.django_db
@pytest.fixture
def general_admin():
    return get_user_model().objects.create(
        username='test_general_admin',
        first_name='Genie',
        last_name='Manager',
        email='genie.manager@example.com',
        is_staff=True,
        is_general_admin=True,
        preferred_language='en'
    )


@pytest.mark.django_db
@pytest.fixture
def group():
    return Group.objects.create(name='test group')


@pytest.mark.django_db
@pytest.fixture
def purpose():
    return Purpose.objects.create(name='test purpose', id='test-purpose')


@pytest.fixture
def resource_group(resource_in_unit):
    group = ResourceGroup.objects.create(
        identifier='test_group',
        name='Test resource group'
    )
    group.resources.set([resource_in_unit])
    return group


@pytest.fixture
def resource_group2(resource_in_unit2):
    group = ResourceGroup.objects.create(
        identifier='test_group_2',
        name='Test resource group 2'
    )
    group.resources.set([resource_in_unit2])
    return group

@pytest.fixture
def test_municipality():
    municipality = Municipality.objects.create(
        id='foo',
        name='Foo'
    )
    return municipality


@pytest.fixture
def accessibility_viewpoint_wheelchair():
    vp = {"id": "10", "name_en": "I am a wheelchair user", "order_text": 10}
    return AccessibilityViewpoint.objects.create(**vp)


@pytest.fixture
def accessibility_viewpoint_hearing():
    vp = {"id": "20", "name_en": "I am hearing impaired", "order_text": 20}
    return AccessibilityViewpoint.objects.create(**vp)


@pytest.fixture
def accessibility_value_green():
    return AccessibilityValue.objects.create(value='green', order=10)


@pytest.fixture
def accessibility_value_red():
    return AccessibilityValue.objects.create(value='red', order=-10)


@pytest.fixture
def resource_with_accessibility_data(resource_in_unit, accessibility_viewpoint_wheelchair,
                                     accessibility_viewpoint_hearing, accessibility_value_green,
                                     accessibility_value_red):
    """ Resource is wheelchair accessible, not hearing accessible, unit is accessible to both """
    ResourceAccessibility.objects.create(
        resource=resource_in_unit,
        viewpoint=accessibility_viewpoint_wheelchair,
        value=accessibility_value_green
    )
    ResourceAccessibility.objects.create(
        resource=resource_in_unit,
        viewpoint=accessibility_viewpoint_hearing,
        value=accessibility_value_red
    )
    UnitAccessibility.objects.create(
        unit=resource_in_unit.unit,
        viewpoint=accessibility_viewpoint_wheelchair,
        value=accessibility_value_green
    )
    UnitAccessibility.objects.create(
        unit=resource_in_unit.unit,
        viewpoint=accessibility_viewpoint_hearing,
        value=accessibility_value_green
    )
    return resource_in_unit


@pytest.fixture
def resource_with_accessibility_data2(resource_in_unit2, accessibility_viewpoint_wheelchair,
                                      accessibility_viewpoint_hearing, accessibility_value_green,
                                      accessibility_value_red):
    """ Resource is hearing accessible, not wheelchair accessible, unit is accessible to both """
    ResourceAccessibility.objects.create(
        resource=resource_in_unit2,
        viewpoint=accessibility_viewpoint_wheelchair,
        value=accessibility_value_red
    )
    ResourceAccessibility.objects.create(
        resource=resource_in_unit2,
        viewpoint=accessibility_viewpoint_hearing,
        value=accessibility_value_green
    )
    UnitAccessibility.objects.create(
        unit=resource_in_unit2.unit,
        viewpoint=accessibility_viewpoint_wheelchair,
        value=accessibility_value_green
    )
    UnitAccessibility.objects.create(
        unit=resource_in_unit2.unit,
        viewpoint=accessibility_viewpoint_hearing,
        value=accessibility_value_green
    )
    return resource_in_unit2


@pytest.fixture
def resource_with_accessibility_data3(resource_in_unit3, accessibility_viewpoint_wheelchair,
                                      accessibility_viewpoint_hearing, accessibility_value_green,
                                      accessibility_value_red):
    """ Resource is accessible, unit is not """
    ResourceAccessibility.objects.create(
        resource=resource_in_unit3,
        viewpoint=accessibility_viewpoint_wheelchair,
        value=accessibility_value_green
    )
    ResourceAccessibility.objects.create(
        resource=resource_in_unit3,
        viewpoint=accessibility_viewpoint_hearing,
        value=accessibility_value_green
    )
    UnitAccessibility.objects.create(
        unit=resource_in_unit3.unit,
        viewpoint=accessibility_viewpoint_wheelchair,
        value=accessibility_value_red
    )
    UnitAccessibility.objects.create(
        unit=resource_in_unit3.unit,
        viewpoint=accessibility_viewpoint_hearing,
        value=accessibility_value_red
    )
    return resource_in_unit3

@pytest.fixture
def maintenance_message():
    return MaintenanceMessage.objects.create(
        start=timezone.now() - datetime.timedelta(hours=1),
        end=timezone.now() + datetime.timedelta(hours=1),
        message='Tämä on ilmoitus',
        message_fi='Tämä on ilmoitus',
        message_en='This is a notice',
        message_sv='Detta är ett meddelande'
    )

@pytest.fixture
def maintenance_mode(maintenance_message):
    return MaintenanceMode.objects.create(
        start=timezone.now(), end=timezone.now() + datetime.timedelta(minutes=20),
        maintenance_message=maintenance_message
    )

@pytest.mark.django_db
@pytest.fixture
def universal_form_field_type():
    return UniversalFormFieldType.objects.create(
        type='Select'
    )

@pytest.mark.django_db
@pytest.fixture
def resource_universal_field_no_options(resource_in_unit, universal_form_field_type):
    return ResourceUniversalField.objects.create(
        name='Selection field',
        resource=resource_in_unit,
        field_type=universal_form_field_type,
        label_fi='Suomenkielinen otsikko kentälle',
        label_en='English header for the field',
        label_sv='Svensk rubrik för fältet',
        description_fi='Suomenkielinen kuvaus kentälle',
        description_en='English description for the field',
        description_sv='Svensk beskrivning för fältet',
    )

@pytest.mark.django_db
@pytest.fixture
def resource_universal_field_with_options(resource_universal_field_no_options):
    options = [
        {'en':'First', 'fi': 'Ensimmäinen', 'sv': 'Första'},
        {'en':'Second', 'fi': 'Toinen', 'sv': 'Andra'},
        {'en':'Third', 'fi': 'Kolmas', 'sv': 'Tredje'},
        {'en':'Fourth', 'fi': 'Neljäs', 'sv': 'Fjärde'},
    ]
    for index, option in enumerate(options):
        ResourceUniversalFormOption.objects.create(
        name=f"{option['en']} option",
        resource_universal_field=resource_universal_field_no_options,
        resource=resource_universal_field_no_options.resource,
        text_fi=option['fi'],
        text_en=option['en'],
        text_sv=option['sv'],
        sort_order = index + 1
        )

    return resource_universal_field_no_options

@pytest.mark.django_db
@pytest.fixture
def resource_with_active_reservations(resource_in_unit):
    Reservation.objects.bulk_create(
        [Reservation(
            resource=resource_in_unit,
            begin=datetime.datetime(year=2115, month=4, day=4, hour=i, minute=0, second=0),
            end=datetime.datetime(year=2115, month=4, day=4, hour=i+1, minute=0, second=0)) \
                for i in range(1,11)
        ])
    return resource_in_unit


@pytest.fixture
def resource_create_data(
    purpose, test_unit,
    space_resource_type):
    image = get_test_image_data()
    return {
        "public": True,
        "purposes": [
            purpose.id
        ],
        "name": {
            "fi": "Test Resource API",
            "en": "Test Resource API",
            "sv": "Test Resource API",
        },
        "description": {
            "fi": "Test Resource created through API",
            "en": "Test Resource created through API",
            "sv": "Test Resource created through API"
        },
        "reservation_info": {
            "fi": "Test Resource reservation information",
            "en": "Test Resource reservation information",
            "sv": "Test Resource reservation information"
        },
        "need_manual_confirmation": False,
        "min_period": "00:30:00",
        "max_period": "01:00:00",
        "slot_size": "00:15:00",
        "authentication": "strong",
        "people_capacity": "10",
        "terms_of_use": [],
        "unit": test_unit.pk,
        "type": space_resource_type.pk,
        "images": [get_test_image_payload(image=image)]
    }


@pytest.fixture
def resource_with_reservable_publish_date(resource_in_unit):
    ResourcePublishDate.objects.create(
        begin=datetime.datetime(year=2100, month=12, day=12),
        end=datetime.datetime(year=2100, month=12, day=13),
        reservable=True,
        resource=resource_in_unit
    )
    return resource_in_unit


@pytest.fixture
def resource_with_not_reservable_publish_date(resource_in_unit):
    ResourcePublishDate.objects.create(
        begin=datetime.datetime(year=2100, month=12, day=12),
        end=datetime.datetime(year=2100, month=12, day=13),
        reservable=False,
        resource=resource_in_unit
    )
    return resource_in_unit
