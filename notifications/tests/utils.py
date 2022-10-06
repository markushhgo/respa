from django.core import mail
from payments.utils import get_price_period_display

def _mail_exists(subject, to, strings, html_body):
    for mail_instance in mail.outbox:
        if subject not in mail_instance.subject:
            continue
        if set(mail_instance.to) != set([to]):
            continue
        mail_message = mail_instance.body
        if all(string in mail_message for string in strings):
            if html_body:
                assert html_body in (a[0] for a in mail_instance.alternatives if a[1] == 'text/html')
            else:
                assert not mail_instance.alternatives
            return True
    return False

def check_mail_was_not_sent():
    assert len(mail.outbox) == 0, "Mails were sent."

def check_received_mail_exists(subject, to, strings, clear_outbox=True, html_body=None):
    if not (isinstance(strings, list) or isinstance(strings, tuple)):
        strings = (strings,)
    assert len(mail.outbox) >= 1, "No mails sent"
    assert _mail_exists(subject, to, strings, html_body)
    if clear_outbox:
        mail.outbox = []

def localize_decimal(d):
    return str(d).replace('.', ',')

def get_expected_strings(order):
    order_line = order.order_lines.first()
    product = order_line.product
    order_details = "[%(details)s]" % ({
        'details': ', '.join([str(x) for x in order.reservation.get_notification_context('fi')['order_details']])
    })
    return (
        order.order_number,
        str(order.created_at.year),
        localize_decimal(order.get_price()),
        localize_decimal(order_line.get_price()),
        str(order_line.quantity),
        localize_decimal(order_line.get_unit_price()),
        order_details,
        product.product_id,
        product.name,
        product.description,
        product.type,
        product.get_type_display(),
        product.price_type,
        product.get_price_type_display(),
        str(product.price_period),
        str(get_price_period_display(product.price_period)),
    )

def get_body_with_all_template_vars():
    template_vars = (
        'order.id',
        'order.created_at',
        'order.price',
        'order_line.price',
        'order_line.quantity',
        'order_line.unit_price',
        'order_details',
        'product.id',
        'product.name',
        'product.description',
        'product.type',
        'product.type_display',
        'product.price_type',
        'product.price_type_display',
        'product.price_period',
        'product.price_period_display',
    )
    body = '{% set order_line=order.order_lines[0] %}{% set product=order_line.product %}\n'
    for template_var in template_vars:
        body += '{{ %s }}\n' % template_var
    return body