import datetime
from copy import deepcopy
from decimal import Decimal
import pytest
from pytz import UTC

from resources.tests.conftest import resource_in_unit  # noqa

from ..models import ARCHIVED_AT_NONE, CustomerGroup, Product, ProductCustomerGroup

@pytest.fixture(autouse=True)
def auto_use_django_db(db):
    pass


@pytest.fixture()
def product_1(resource_in_unit):
    product = Product.objects.create(
        name_en='test product 1',
        sku='1',
        price=Decimal('12.81')
    )
    product.resources.set([resource_in_unit])
    return product


@pytest.fixture()
def product_2():
    return Product.objects.create(
        name_en='test product 2',
        sku='2',
        price=Decimal('20.00')
    )

@pytest.fixture()
def product_1_v2(product_1):
    product_1_v2 = deepcopy(product_1)
    product_1_v2.name_en = 'test product 1 version 2'
    product_1_v2.save()
    product_1.refresh_from_db()
    return product_1_v2


@pytest.mark.django_db
def test_product_customer_group(product_with_multiple_product_cg):
    assert ProductCustomerGroup.objects.filter(product=product_with_multiple_product_cg).count() == 5

@pytest.mark.django_db
def test_duplicate_customer_group(customer_group):
    obj, created = CustomerGroup.objects.get_or_create(name=customer_group.name)
    assert not created
    assert obj == customer_group


@pytest.mark.django_db
def test_multiple_customer_groups(customer_groups):
    for customer_group in customer_groups:
        obj, created = CustomerGroup.objects.get_or_create(name=customer_group.name)
        assert not created
        assert obj == customer_group

def test_product_creation(product_1, product_2, resource_in_unit):
    assert product_1.product_id != product_2.product_id
    assert Product.objects.count() == 2
    assert Product.objects.current().count() == 2
    assert set(product_1.resources.all()) == {resource_in_unit}


def test_product_update(product_1, product_1_v2, resource_in_unit):
    assert Product.objects.all().count() == 2
    assert Product.objects.current().count() == 1

    assert product_1.name_en == 'test product 1'
    assert product_1.archived_at != ARCHIVED_AT_NONE
    assert set(product_1.resources.all()) == {resource_in_unit}

    assert product_1_v2.name_en == 'test product 1 version 2'
    assert product_1_v2.archived_at == ARCHIVED_AT_NONE
    assert set(product_1_v2.resources.all()) == {resource_in_unit}


def test_product_delete(product_1_v2, product_2):
    product_1_v2.delete()

    assert Product.objects.count() == 3
    assert set([p.id for p in Product.objects.current()]) == {product_2.id}


def test_get_pretax_price_success(product_1):
    """Test the price calculation logic is correct when retrieving product pretax price

    Includes tax and is rounded to two decimals"""
    assert product_1.get_pretax_price() == Decimal('10.33')


def test_get_price_for_time_range_success(product_1):
    """Test the price calculation works correctly with timestamps"""
    start = datetime.datetime(2119, 5, 5, 10, 0, 0, tzinfo=UTC)
    end = datetime.datetime(2119, 5, 5, 11, 30, 0, tzinfo=UTC)
    rounded = product_1.get_price_for_time_range(start, end)
    not_rounded = product_1.get_price_for_time_range(start, end, rounded=False)
    assert rounded == Decimal('19.22')
    assert not_rounded == Decimal('19.215')


def test_get_pretax_price_for_time_range_success(product_1):
    """Test the pretax price calculation works correctly with timestamps"""
    start = datetime.datetime(2119, 5, 5, 10, 0, 0, tzinfo=UTC)
    end = datetime.datetime(2119, 5, 5, 13, 0, 0, tzinfo=UTC)
    rounded = product_1.get_pretax_price_for_time_range(start, end)
    not_rounded = product_1.get_pretax_price_for_time_range(start, end, rounded=False)
    assert rounded == Decimal('30.99')
    assert not_rounded.quantize(Decimal('0.00001')) == Decimal('30.99194')


def test_get_price_for_reservation_success(product_1, two_hour_reservation):
    """Test the time range is correctly extracted from reservation to use in price calculation with tax"""
    rounded = product_1.get_price_for_reservation(two_hour_reservation)
    not_rounded = product_1.get_price_for_reservation(two_hour_reservation, rounded=False)
    assert rounded == Decimal('25.62')
    assert not_rounded == Decimal('25.62')


def test_get_pretax_price_for_reservation_success(product_1, two_hour_reservation):
    """Test the time range is correctly extracted from reservation to use in price calculation without tax"""
    rounded = product_1.get_pretax_price_for_reservation(two_hour_reservation)
    not_rounded = product_1.get_pretax_price_for_reservation(two_hour_reservation, rounded=False)
    assert rounded == Decimal('20.66')
    assert not_rounded.quantize(Decimal('0.00001')) == Decimal('20.66129')


def test_get_detailed_price_for_time_range_per_period_timeslots_quantity(product_with_pcgs_and_time_slot_prices):
    """Test quantity is added correctly to detailed pricing with per period products with timeslots"""
    begin = datetime.datetime(2119, 5, 5, 10, 0, 0, tzinfo=UTC)
    end = datetime.datetime(2119, 5, 5, 12, 0, 0, tzinfo=UTC)

    result = product_with_pcgs_and_time_slot_prices.get_detailed_price_for_time_range(begin, end, quantity=0)
    assert 'quantity' not in result['default']

    result = product_with_pcgs_and_time_slot_prices.get_detailed_price_for_time_range(begin, end, quantity=1)
    assert 'quantity' not in result['default']

    result = product_with_pcgs_and_time_slot_prices.get_detailed_price_for_time_range(begin, end, quantity=2)
    assert 'quantity' in result['default']
    assert result['default']['quantity'] == 2


def test_get_detailed_price_for_time_range_per_period_no_timeslots_quantity(product_with_no_price_product_cg):
    """Test quantity is added correctly to detailed pricing with per period products without timeslots"""
    begin = datetime.datetime(2119, 5, 5, 10, 0, 0, tzinfo=UTC)
    end = datetime.datetime(2119, 5, 5, 12, 0, 0, tzinfo=UTC)

    result = product_with_no_price_product_cg.get_detailed_price_for_time_range(begin, end, quantity=0)
    assert 'quantity' not in result['default']

    result = product_with_no_price_product_cg.get_detailed_price_for_time_range(begin, end, quantity=1)
    assert 'quantity' not in result['default']

    result = product_with_no_price_product_cg.get_detailed_price_for_time_range(begin, end, quantity=2)
    assert 'quantity' in result['default']
    assert result['default']['quantity'] == 2
