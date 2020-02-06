from exchangelib import Account, Credentials, EWSDateTime, EWSTimeZone
from datetime import datetime, timedelta
from time import sleep

import threading

class RespaOutlookManager:
    def __init__(self, configuration):
        self.configuration = configuration
        self.account = None
        self.pop_from_store = False
        self.managed_calendar = None
        self.manage = False
        try:
            self.account = Account(configuration.email, credentials=Credentials(configuration.email, configuration.password), autodiscover=True)
            self.calendar = self.account.calendar.all()
            self.thread = threading.Thread(target=self._manage_managed_calendar)
            self.thread.start()
        except:
            self.pop_from_store = True

    def refresh(self):
        self.calendar = self.account.calendar.all()
        return self.calendar

    def future(self):
        self.calendar = self.calendar.filter(end__gte=ToEWSDateTime(datetime.now().replace(microsecond=0)))
        return self.calendar
    
    def all(self):
        return self.managed_calendar

    def _manage_managed_calendar(self):
        self.manage = True
        while self.manage:
            self.managed_calendar = self.account.calendar.all()
            sleep(20)
    
    def _calendar(self):
        return self.account.calendar


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