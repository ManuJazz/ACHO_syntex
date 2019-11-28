#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import configparser
import threading
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import io
import os
import os.path
import json
import time
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
import logging

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"


class SnipsConfigParser(configparser.SafeConfigParser):
    def to_dict(self):
        return {section: {option_name: option for option_name, option in self.items(section)} for section in
                self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding=CONFIGURATION_ENCODING_FORMAT) as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, configparser.Error) as e:
        return dict()


def say(intentMessage, text):
    mqttClient.publish_start_session_notification(intentMessage, text, None)


# mqttClient.publish_start_session_action(site_id='default', session_init_text = 'Te la has tomado', session_init_intent_filter = ["ManuJazz:Affirmation", "ManuJazz:Negation"], session_init_can_be_enqueued=True, session_init_send_intent_not_recognized=True, custom_data=None)


def recordatorio(intentMessage, e):
    print("Evento detectado para: %s" % datetime.now())
    say(intentMessage, "Hola. A esta hora debes tomar " + e.med + ". " + e.description)
    content = "[" + str(datetime.today()) + "] Reminder announced: " + e.med + "\n"
    print(content)
    mqttClient.publish_start_session_action(site_id=intentMessage, session_init_text=u'¿Te la has tomado?',
                                            session_init_intent_filter=["ManuJazz:Affirmation", "ManuJazz:Negation"],
                                            session_init_can_be_enqueued=True,
                                            session_init_send_intent_not_recognized=True, custom_data=None)
    with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
        text_file.write(content)
    identity = e.med
    backReminder.add_job(recordatorio, 'interval', seconds=20, id=identity, args=['default', e])


def appointment_reminder(intentMessage, appointment):
    print("Evento detectado para: %s" % datetime.now())
    say(intentMessage,
        "Hola. Te recuerdo que manana a esta hora tienes una cita con el " + appointment.subject + " en " + appointment.place)
    content = "[" + str(
        datetime.today()) + "] Appointment announced: " + appointment.subject + " (" + appointment.place + ")\n"
    print(content)
    with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
        text_file.write(content.encode('utf-8'))


class Event(object):
    def __init__(self, med, fecha, description):
        self.med = med
        self.fecha = fecha
        self.description = description


class Appointment(object):
    def __init__(self, subject, place, date, hour):
        self.subject = subject
        self.place = place
        self.date = date
        self.hour = hour


class update_prescriptions(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/Madrid'})
        scheduler.start()

        time.sleep(10)
        with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
            content = "[Thread restarted] [Trying... first announce]"
            text_file.write(content)
        # say('Announce', "Hola. Ya estoy operativo y listo para ayudarte.")

        with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
            content = "[Done... first announce]\n"
            text_file.write(content)
        # checks constantly
        while True:
            # if there’s a file to process
            filename = "/bluetooth/full_information.txt"
            if os.path.isfile(filename):
                scheduler.shutdown(wait=False)
                scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/Madrid'})
                scheduler.start()
                with open(filename, 'r') as f:
                    datastore = json.load(f)
                    print(datastore)
                    # obtains full info from file
                    for data in datastore['appointments']:
                        # 1. Appointments
                        subject = data['subject']
                        place = data['place']
                        date = data['date']
                        hour = data['hour']
                        date = date.replace('/', '-')
                        date = date.split("-")
                        date = date[2] + "-" + date[1] + "-" + date[0] + " " + hour + ":00"
                        date2 = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                        prev = date2 - timedelta(1)
                        a = Appointment(subject, place, prev, hour)
                        print(prev)
                        scheduler.add_job(appointment_reminder, 'date', run_date=prev, id=date, args=['default', a],
                                          max_instances=10000)
                        logging.basicConfig()

                    for prescription in datastore['prescriptions']:
                        # 2. Prescription
                        name = prescription['medicine']
                        description = prescription['description']
                        for take in prescription['takes']:
                            print(name)
                            print(description)
                            print(take)
                            now = datetime.now()
                            dt_string = now.strftime("%Y-%m-%d")
                            # fecha = "2019-10-08+" "+ take
                            fecha = dt_string + " " + take
                            date = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")
                            med = name
                            e = Event(med, date, description)
                            identity = fecha + " - " + med
                            scheduler.add_job(recordatorio, 'interval', days=1, start_date=date, id=identity,
                                              args=['default', e], max_instances=10000)
                            logging.basicConfig()
                os.system('mv /bluetooth/full_information.txt /var/lib/snips/skills/ManuJazz.ACHOSintex/old_content')
                with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
                    content = "[Trying... sync done announce]"
                    text_file.write(content)
                say('default',
                    u"Sincronización detectada. Ahora las prescripciones y los medicamentos se han actualizado.")
                with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
                    content = "[Done... sync done announce]\n"
                    text_file.write(content)
            time.sleep(1)


def subscribe_taken_medicine(hermes, intentMessage):
    conf = read_configuration_file(CONFIG_INI)
    backReminder.remove_all_jobs(None)
    mqttClient.publish_end_session(intentMessage.session_id, 'Ok. Me lo apunto')


def subscribe_not_taken_medicine(hermes, intentMessage):
    conf = read_configuration_file(CONFIG_INI)
    mqttClient.publish_end_session(intentMessage.session_id, u'Ok. Te lo recordaré dentro de un momento')


if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    thread = update_prescriptions()
    thread.start()

    backReminder = BackgroundScheduler({'apscheduler.timezone': 'Europe/Madrid'})
    backReminder.start()

    logging.basicConfig(filename='app.log', filemode='w')
    logging.info('main loaded')
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
            content = "[Load ready]\n"
            text_file.write(content)
        h \
            .subscribe_intent("ManuJazz:Affirmation", subscribe_taken_medicine) \
            .subscribe_intent("ManuJazz:Negation", subscribe_not_taken_medicine) \
            .start()
        print("out")
