from django.conf import settings

from respa_outlook.models import RespaOutlookReservation
from django.core.exceptions import ValidationError

from time import sleep, time
from copy import copy
import threading

class Listen():
    def __init__(self, store):
        self.store = store
        self.configs = store.items
        self.status = False
        self.creating = False
        self.modifying = False
        self.thread = threading.Thread(target=self.start)
        self.manager = None
        self.config = None
        self.calendar = None
        self.thread.start()

    def start(self):
        self.status = True
        while self.status:
            pop = []

            configs = copy(self.configs) # Avoid RunTimeError this way

            for manager in configs:
                self.manager = self.configs[manager]
                if self.manager.pop_from_store:
                    pop.append(self.manager)
                    continue

                self.config = self.manager.configuration
                self.calendar = copy(self.manager.future())

                assert self.manager is not None
                assert self.config is not None
                assert self.calendar is not None

                self.__handle_add()
                self.__handle_modify()
                self.__handle_remove()

                self.manager = None
                self.config = None
                self.calendar = None

            for manager in pop:
                self.configs.pop(manager.configuration.id)
            sleep(settings.OUTLOOK_POLLING_RATE)
    
    def stop(self):
        self.status = False


    def __handle_remove(self):
        for appointment in self.calendar:
            if not self.creating:
                try:
                    reservation = RespaOutlookReservation.objects.get(exchange_id=appointment.id)
                    if reservation.reservation.state == 'cancelled':
                        appointment.delete()
                        reservation.delete()
                except:
                    pass
        for reservation in RespaOutlookReservation.objects.all():
            if self.is_missing_from_calendar(reservation.exchange_id):
                reservation.reservation.state = 'cancelled'
                reservation.reservation.save()
                reservation.delete()

    
    def __handle_add(self):
        for appointment in self.calendar:
            try:
                reservation = RespaOutlookReservation.objects.get(exchange_id=appointment.id)
                if reservation.reservation.state == 'cancelled':
                    appointment.delete()
                    reservation.delete()
                continue
            except Exception as ex:
                pass
            try:
                email = appointment.required_attendees[0].mailbox.email_address
            except Exception as ex:
                continue

            self.creating = True
            try: 
                self.config.create_respa_outlook_reservation(
                    appointment = appointment,
                    reservation = None,
                    email = email
                )
            except ValidationError:
                appointment.delete()
            self.creating = False
    
    def __handle_modify(self):
        old_ids = {}
        for reservation in RespaOutlookReservation.objects.all():
            if reservation.exchange_id not in old_ids:
                old_ids.update({
                    reservation.exchange_id : {
                        
                    }
                })
                    # Always unique      
            old_ids[reservation.exchange_id].update({
                'id': reservation.reservation.id,
                'change_key': reservation.exchange_id,
                'begin': reservation.reservation.begin,
                'end': reservation.reservation.end,
                'reservation': reservation.reservation,
                'modified_timestamp': reservation.get_modified_timestamp()
            })
        for appointment in self.calendar:
            _dict = old_ids.get(appointment.id)
            if _dict:
                if _dict.get('modified_timestamp') > int(time()):
                    continue

                if _dict.get('begin') != appointment.start:
                    if not self.modifying:
                        self.modifying = True
                        self.config.handle_modify(_dict.get('reservation'), appointment)
                        self.modifying = False
                    continue
                
                if _dict.get('end') != appointment.end:
                    if not self.modifying:
                        self.modifying = True
                        self.config.handle_modify(_dict.get('reservation'), appointment)
                        self.modifying = False
                    continue


    def is_missing_from_calendar(self, id):
        for appointment in self.manager.calendar.all():
            if appointment.id == id:
                return False
        return True
