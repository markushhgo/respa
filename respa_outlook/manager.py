from exchangelib import Account, Credentials, EWSDateTime, EWSTimeZone, DELEGATE
from exchangelib.errors import ErrorSchemaValidation
from datetime import datetime, timedelta
from time import sleep

import threading

class RespaOutlookManager:
    def __init__(self, configuration):
        self.configuration = configuration
        self.account = None
        self.pop_from_store = False
        try:
            self.account = self._get_account()
            self.calendar = self.account.calendar
        except:
            self.pop_from_store = True

    def future(self):
        return self.account.calendar.filter(end__gte=ToEWSDateTime(datetime.now().replace(microsecond=0)))

    def _get_account(self):
        if not self.account:
            self.account = Account(primary_smtp_address=self.configuration.email, credentials=Credentials(self.configuration.email, self.configuration.password), autodiscover=True, access_type=DELEGATE)
        else:
            ews_url = self.account.protocol.service_endpoint
            ews_auth_type = self.account.protocol.auth_type
            primary_smtp_address = self.account.primary_smtp_address

            # You can now create the Account without autodiscovering, using the cached values:
            config = Configuration(service_endpoint=ews_url, credentials=Credentials(self.configuration.email, self.configuration.password), auth_type=ews_auth_type)
            self.account = Account(
                primary_smtp_address=primary_smtp_address, 
                config=config, autodiscover=False, 
                access_type=DELEGATE,
            )
        return self.account


"""
Store configurations here on startup
"""
store = {}




def ToEWSDateTime(_datetime, send_to_ews=False):
    tz = EWSTimeZone.timezone('Europe/Helsinki')
    time = tz.localize(
        EWSDateTime(
            year=_datetime.year,
            month=_datetime.month,
            day=_datetime.day,
            hour=_datetime.hour,
            minute=_datetime.minute
        )
    )
    if send_to_ews:
        _magic = str(time).split('+')[1].split(':')[0]
        time = time + timedelta(hours=int(_magic))
    return time