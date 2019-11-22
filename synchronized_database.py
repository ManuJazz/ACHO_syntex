# -*- coding: utf-8 -*-
import json
import logging
import os
import os.path
import threading
import time

import mysql.connector as mariadb

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from hermes_python.ffi.utils import MqttOptions
from hermes_python.hermes import Hermes
from hermes_python.ontology import *

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

# database connection
mariadb_connection = mariadb.connect(user='root', password='', database='AchoSintex')
cursor = mariadb_connection.cursor()


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

def clean_appointments():
    query="DELETE FROM Appointment;"
    cursor.execute(query)
    mariadb_connection.commit()

def clean_prescriptions():
    query = "DELETE FROM Prescription;"
    cursor.execute(query)
    mariadb_connection.commit()

def say(intentMessage, text):
    mqttClient.publish_start_session_notification(intentMessage, text, None)


def prescription_reminder(intentMessage, prescription):
    print("Evento detectado para: %s" % datetime.now())
    say(intentMessage, "Hola. A esta hora debes tomar " + prescription.med + ". " + prescription.description)
    content = "[" + str(datetime.today()) + "] Reminder announced: " + e.med + "\n"
    print(content)
    with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
        text_file.write(content)


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


class User(object):
    def __init__(self, name, birthdate, location):
        self.name = name
        self.birthdate = birthdate
        self.location = location


class Prescription(object):
    def __init__(self, medicine, description, days, takes):
        self.medicine = medicine
        self.description = description
        self.days = days
        self.takes = takes


class update_prescriptions(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

#    def say(intentMessage, text):
#        mqttClient.publish_start_session_notification(intentMessage, text, None)

    def run(self):
        scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/Madrid'})
        scheduler.start()
        time.sleep(2)
	with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
            content = "[Trying... first announce]\n"
            text_file.write(content)
	say('default', "Hola. Ya estoy operativo y listo para ayudarte.")
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
                        insert_appointment(a)
                        print(prev)
                        scheduler.add_job(appointment_reminder, 'date', run_date=prev, id=date, args=['default', a],
                                          max_instances=10000)
                        logging.basicConfig()

                    for prescription in datastore['prescriptions']:
                        # 2. Prescription
                        name = prescription['medicine']
                        description = prescription['description']
			prescription_instance = Prescription(name, description, "[]", str(prescription['takes']))
			insert_prescription(prescription_instance)
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
                            scheduler.add_job(prescription_reminder, 'interval', days=1, start_date=date, id=identity,
                                              args=['default', e], max_instances=10000)
                            logging.basicConfig()
                os.system('mv /bluetooth/full_information.txt /var/lib/snips/skills/ManuJazz.ACHOSintex/old_content')
		#say('default', "Sincronizacion detectada. Ahora las prescripciones y citas estan actualizadas.")
            time.sleep(1)


if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    thread = update_prescriptions()
    thread.start()
    logging.basicConfig(filename='app.log', filemode='w')
    logging.info('main loaded')

    #Clean stored data
    clean_prescriptions()
    clean_appointments()

    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
	    content = "[Load ready]\n"
            text_file.write(content)
	h.start()
        print("out")

