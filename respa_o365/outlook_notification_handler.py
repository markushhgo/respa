import json
import logging

from django.conf import settings
from django.db import Error
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from respa_o365.calendar_sync import add_to_queue, ensure_notification
from respa_o365.models import OutlookCalendarLink, OutlookCalendarReservation
from respa_o365.o365_calendar import MicrosoftApi, O365Calendar

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class NotificationCallback(View):
    """
    Endpoint to receive notifications from Microsoft Graph API.
    https://docs.microsoft.com/en-us/graph/webhooks
    """
    # TODO Call synchronisation with received changes.

    def post(self, request):
        if self.is_validation_request(request):
            return self.handle_validation_request(request)
        if self.is_notification(request):
            return self.handle_notification(request)
        return self.http_method_not_allowed(request)
    pass

    def is_validation_request(self, request):
        validation_token = request.GET.get('validationToken')
        return validation_token is not None and len(request.GET) == 1

    def handle_validation_request(self, request):
        validation_token = request.GET.get('validationToken')
        return HttpResponse(content=validation_token, content_type='text/plain', status=200)

    def is_notification(self, request):
        if request.content_type != 'application/json':
            return False
        return request.body.startswith(b'{')

    def handle_notification(self, request):
        notifications = json.loads(request.body).get("value")
        try:
            for notification in notifications:
                sub_id = notification.get("subscriptionId")
                link = OutlookCalendarLink.objects.filter(exchange_subscription_id=sub_id).first()
                res_data = notification.get("resourceData")
                if not link:
                    logger.info("Received notification from subscription %s not connected to any calendar link.", sub_id)
                    continue
                elif link.exchange_subscription_secret != notification.get("clientState"):
                    logger.warning("Notification from subscription %s has wrong subscription secret.", sub_id)
                    continue
                elif not res_data:
                    # It's a different kind of notification
                    ls_event = notification.get("lifecycleEvent")
                    if ls_event == "subscriptionRemoved":
                        logger.info("Renewing notification for subscription %s", sub_id)
                        ensure_notification(link)
                        continue
                    logger.info("Unknown type of notification for subscription %s", sub_id)
                    continue

                exchange_id = res_data.get("id")
                mapping = OutlookCalendarReservation.objects.filter(exchange_id=exchange_id).first()
                if mapping:
                    api = MicrosoftApi(link.token)
                    cal = O365Calendar(microsoft_api=api, event_prefix=settings.O365_CALENDAR_RESERVATION_EVENT_PREFIX)
                    item = cal.get_event(exchange_id)
                    if item and item.change_key() == mapping.exchange_change_key:
                        continue

                logger.info("Handling notifications from subscription %s. Syncing resource %s for user %d",
                                sub_id, link.resource_id, link.user_id)
                add_to_queue(link)


        except Error as e:
            logger.warning("Notification handling failed: %s", str(e))
        return HttpResponse(status=202)





