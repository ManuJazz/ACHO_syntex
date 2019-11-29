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
import mysql.connector as mariadb

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
import logging

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

# database connection
mariadb_connection = mariadb.connect(user='root', password='', database='AchoSintex')
cursor = mariadb_connection.cursor()
global_prescription = None


def insert_prescription(prescription):
    query = "INSERT INTO Prescription(medicine, description, days, takes) VALUES (%s, %s, %s, %s)"
    args = (prescription.medicine, prescription.description, prescription.days, prescription.takes)
    cursor.execute(query, args)
    mariadb_connection.commit()


def insert_appointment(appointment):
    query = "INSERT INTO Appointment(subject, place, day, time) VALUES (%s, %s, %s, %s)"
    args = (appointment.subject, appointment.place, appointment.date, appointment.hour)
    cursor.execute(query, args)
    mariadb_connection.commit()


def insert_taken(take):
    query = "INSERT INTO Taken(medicine, day, hour, taken) VALUES (%s, %s, %s, %s)"
    args = (take.medicine, take.day, take.hour, take.taken)
    cursor.execute(query, args)
    mariadb_connection.commit()


def clean_appointments():
    query = "DELETE FROM Appointment;"
    cursor.execute(query)
    mariadb_connection.commit()


def clean_prescriptions():
    query = "DELETE FROM Prescription;"
    cursor.execute(query)
    mariadb_connection.commit()


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


def prescription_reminder(intentMessage, prescription):
    global global_prescription
    global_prescription = prescription
    print("Evento detectado para: %s" % datetime.now())
    say(intentMessage, "Hola. A esta hora debes tomar " + prescription.medicine + ". " + prescription.description)
    content = "[" + str(datetime.today()) + "] Reminder announced: " + prescription.medicine + "\n"
    print(content)
    mqttClient.publish_start_session_action(site_id=intentMessage, session_init_text=u'¿Te la has tomado?',
                                            session_init_intent_filter=["ManuJazz:Affirmation", "ManuJazz:Negation"],
                                            session_init_can_be_enqueued=True,
                                            session_init_send_intent_not_recognized=True, custom_data=None)

    # reminder is saved
    with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
        text_file.write(content)

    # notices are incremented
    global_prescription.notices = global_prescription.notices + 1
    # check if first time announced
    identity = global_prescription.medicine
    if global_prescription.notices == 1:
        # if it's first time -> add back reminder!
        backReminder.add_job(prescription_reminder, 'interval', seconds=40, id=identity,
                         args=['default', global_prescription])

    # check if it's been three time announced
    if global_prescription.notices == 3:
        backReminder.remove_job(identity)


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


class Prescription(object):
    def __init__(self, medicine, description, days, take):
        self.medicine = medicine
        self.description = description
        self.days = days
        self.takes = take
        self.notices = 0


class Taken(object):
    def __init__(self, medicine, day, hour, taken):
        self.medicine = medicine
        self.day = day
        self.hour = hour
        self.taken = taken


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
                clean_prescriptions()
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
                            prescription = Prescription(name, description, fecha, take)
                            identity = fecha + " - " + med
                            scheduler.add_job(prescription_reminder, 'interval', days=1, start_date=date, id=identity,
                                              args=['default', prescription], max_instances=10000)
                            logging.basicConfig()
                            # insertion prescription
                            insert_prescription(prescription)

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
    global global_prescription
    if global_prescription is not None:
        # back reminder is deleted
        identity = global_prescription.medicine
        backReminder.remove_job(identity)

        # medicine take is registered
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d")
        take = Taken(global_prescription.medicine, dt_string, global_prescription.takes, "1")
        insert_taken(take)
        global_prescription.notices = 0
        mqttClient.publish_end_session(intentMessage.session_id, 'Perfecto. Me lo apunto')


def subscribe_not_taken_medicine(hermes, intentMessage):
    if global_prescription is not None:
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d")
        take = Taken(global_prescription.medicine, dt_string, global_prescription.takes[:-3], "0")
        insert_taken(take)
        mqttClient.publish_end_session(intentMessage.session_id, u'De acuerdo. Te lo recordaré dentro de un momento')
        '''
        if global_prescription.notices == 1:
            identity = global_prescription.medicine
        '''


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
