from respa_outlook.models import RespaOutlookReservation
from time import sleep, time
from copy import copy

import queue
import threading



# TODO: Add queueing

class Listen():
    def __init__(self, configs = {}):
        self.configs = configs
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
            for manager in self.configs:
                self.manager = self.configs[manager]
                self.config = self.manager.configuration
                self.calendar = copy(self.manager.future())

                assert self.calendar is not None

                self.__handle_add()
                self.__handle_modify()
                self.__handle_remove()

                self.manager = None
                self.config = None
                self.calendar = None
            sleep(30)
    
    def stop(self):
        self.status = False


    def __handle_remove(self):
        sleep(5)
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
        sleep(5)
        for appointment in self.calendar:
            try:
                reservation = RespaOutlookReservation.objects.get(exchange_id=appointment.id)
                if reservation.reservation.state == 'cancelled':
                    appointment.delete()
                    reservation.delete()
                continue
            except:
                pass
            try:
                email = appointment.required_attendees[0].mailbox.email_address
            except:
                continue

            self.creating = True
            self.config.create_respa_outlook_reservation(
                appointment = appointment,
                reservation = None,
                email = email
            )
            self.creating = False
    
    def __handle_modify(self):
        sleep(5)
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
                if _dict.get('modified_timestamp') > time():
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
        for appointment in self.manager.all():
            if appointment.id == id:
                return False
        return True