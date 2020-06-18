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
import socket
import subprocess

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
import logging

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

# database connection
cursor = None
global_prescription = None
mariadb_connection = None
closed_connection = True

remote_connection = None
remote_cursor = None
closed_remote_connection = True

REMOTE_USER = "productor"
REMOTE_PASSWORD = "r4D1cando5"
REMOTE_HOSTNAME = "achosintex.spilab.es"
REMOTE_DATABASE = "achosintex"

LOCAL_USER = "root"
LOCAL_PASSWORD = ""
LOCAL_HOSTNAME = "localhost"
LOCAL_DATABASE = "AchoSintex"


def insert_person(person):
    global cursor
    global mariadb_connection
    query = "INSERT INTO User(name, birthdate, location) VALUES (%s, %s, %s)"
    args = (person.name_person, person.birthdate_person, person.place_person)
    cursor.execute(query, args)
    mariadb_connection.commit()


def insert_prescription(prescription):
    global cursor
    global mariadb_connection
    query = "INSERT INTO Prescription(medicine, description, days, takes, user_name) VALUES (%s, %s, %s, %s, %s)"
    args = (
        prescription.medicine, prescription.description, prescription.days, prescription.takes, prescription.user_name)
    cursor.execute(query, args)
    mariadb_connection.commit()


def insert_appointment(appointment):
    global cursor
    global mariadb_connection
    query = "INSERT INTO Appointment(subject, place, day, time, user_name) VALUES (%s, %s, %s, %s, %s)"
    args = (appointment.subject, appointment.place, appointment.date, appointment.hour, appointment.user_name)
    cursor.execute(query, args)
    mariadb_connection.commit()


def insert_taken(take):
    global cursor
    global mariadb_connection
    global closed_connection
    if closed_connection is True:
        connect_database()

    query = "INSERT INTO Taken(medicine, day, hour, taken) VALUES (%s, %s, %s, %s)"
    args = (take.medicine, take.day, take.hour[:-3], take.taken)
    cursor.execute(query, args)
    mariadb_connection.commit()
    disconnect_database()


def clean_appointments():
    global cursor
    global mariadb_connection
    query = "DELETE FROM Appointment;"
    cursor.execute(query)
    mariadb_connection.commit()


def clean_prescriptions():
    global cursor
    global mariadb_connection
    query = "DELETE FROM Prescription;"
    cursor.execute(query)
    mariadb_connection.commit()


def clean_users():
    global cursor
    global global_prescription
    query = "DELETE FROM User;"
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
    connect_database()

    print("Evento detectado para: %s" % datetime.now())

    say(intentMessage,
        "Hola, " + prescription.user_name + ". A esta hora debes tomar " + prescription.medicine + ". " + prescription.description)
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
        # registered as not answered
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d")
        take = Taken(global_prescription.medicine, dt_string, global_prescription.takes, "2",
                     global_prescription.id_user_remote)
        insert_taken(take)
        global_prescription.notices = 0

        if check_internet_connection() and take.id_user_remote != -1:
            connect_remote_database()
            insert_remote_taken(take)

        # mqttClient.publish_end_session(intentMessage.session_id, u'Supongo que no estás en casa. ¡Lo apunto!')
        # global_prescription = None


def appointment_reminder(intentMessage, appointment):
    print("Evento detectado para: %s" % datetime.now())
    say(intentMessage,
        "Hola, " + appointment.user_name + ". Te recuerdo que manana a esta hora tienes una cita con el " + appointment.subject + " en " + appointment.place)
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
    def __init__(self, subject, place, date, hour, user_name):
        self.subject = subject
        self.place = place
        self.date = date
        self.hour = hour
        self.user_name = user_name


class Prescription(object):
    def __init__(self, medicine, description, days, take, user_name, id_user_remote):
        self.medicine = medicine
        self.description = description
        self.days = days
        self.takes = take
        self.notices = 0
        self.user_name = user_name
        self.id_user_remote = id_user_remote


class Taken(object):
    def __init__(self, medicine, day, hour, taken, id_user_remote):
        self.medicine = medicine
        self.day = day
        self.hour = hour
        self.taken = taken
        self.id_user_remote = id_user_remote


class Person(object):
    def __init__(self, name_person, birthdate_person, place_person):
        self.name_person = name_person
        self.birthdate_person = birthdate_person
        self.place_person = place_person


def connect_database():
    global mariadb_connection
    global cursor
    global closed_connection
    mariadb_connection = mariadb.connect(host=LOCAL_HOSTNAME, user=LOCAL_USER, password=LOCAL_PASSWORD,
                                         database=LOCAL_DATABASE,
                                         connection_timeout=20)
    cursor = mariadb_connection.cursor()
    closed_connection = False


def disconnect_database():
    global mariadb_connection
    global cursor
    global closed_connection
    cursor.close()
    mariadb_connection.close()
    closed_connection = True


def insert_remote_taken(take):
    global remote_cursor
    global remote_connection
    global closed_remote_connection
    if closed_remote_connection is True:
        connect_remote_database()

    query = "INSERT INTO Taken(id_medicine, Medicine_common_name, hour, answer, day, id_user) VALUES (%s, %s, %s, %s, %s, %s)"
    args = ('1', take.medicine, take.hour[:-3], take.taken, take.day, take.id_user_remote)
    remote_cursor.execute(query, args)
    remote_connection.commit()
    disconnect_remote_database()


def connect_remote_database():
    global remote_connection
    global remote_cursor
    global closed_remote_connection
    remote_connection = mariadb.connect(host=REMOTE_HOSTNAME, user=REMOTE_USER, password=REMOTE_PASSWORD,
                                        database=REMOTE_DATABASE,
                                        connection_timeout=20)
    remote_cursor = remote_connection.cursor()
    closed_remote_connection = False


def disconnect_remote_database():
    global remote_connection
    global remote_cursor
    global closed_remote_connection
    remote_cursor.close()
    remote_connection.close()
    closed_remote_connection = True


def check_internet_connection():
    IPaddress = socket.gethostbyname(socket.gethostname())
    if IPaddress == "127.0.0.1":
        return False
    else:
        return True


class update_prescriptions(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/Madrid'})
        scheduler.start()

        time.sleep(10)
        global cursor
        global mariadb_connection

        while subprocess.Popen('service mysqld status', shell=True, stdout=subprocess.PIPE).stdout.read().decode(
                'utf-8').find('Active: active') == -1:
            time.sleep(1)

        os.system('cp /var/lib/snips/skills/ManuJazz.ACHOSintex/old_content.txt /bluetooth/full_information.txt')

        # once mysql is ready it will break out of while loop and continue to
        with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
            content = "[Thread restarted] [Trying... first announce]"
            text_file.write(content)
        say('Announce', "Hola. Ya estoy operativo y listo para ayudarte.")

        with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
            content = "[Done... first announce]\n"
            text_file.write(content)
        # checks constantly
        while True:
            # if there’s a file to process
            filename = "/bluetooth/full_information.txt"

            file_procesed = False

            if os.path.isfile(filename):
                connect_database()

                scheduler.shutdown(wait=False)
                scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/Madrid'})
                scheduler.start()
                clean_prescriptions()
                clean_appointments()
                clean_users()
                with open(filename, 'r') as f:
                    try:
                        datastore = json.load(f)
                        # datastore = json.load(f, 'utf-8')
                        print(datastore)
                        # obtains full info from file
                        for person in datastore['personList']:
                            # id_person = person['id_person']
                            name_person = person['name_person']
                            birthdate_person = person['birthdate_person']
                            place_person = person['place_person']
                            p = Person(name_person, birthdate_person, place_person)
                            insert_person(p)

                            for data in person['appointments']:
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
                                a = Appointment(subject, place, prev, hour, person['name_person'])
                                print(prev)
                                scheduler.add_job(appointment_reminder, 'date', run_date=prev, id=date,
                                                  args=['default', a],
                                                  max_instances=10000)
                                logging.basicConfig()

                            for prescription in person['prescriptions']:
                                # 2. Prescription
                                name = prescription['medicine']
                                description = prescription['description']
                                for take in prescription['takes']:
                                    print(name)
                                    print(description.encode('utf-8'))
                                    print(take)
                                    now = datetime.now()
                                    dt_string = now.strftime("%Y-%m-%d")
                                    # fecha = "2019-10-08+" "+ take
                                    fecha = dt_string + " " + take
                                    date = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")
                                    med = name
                                    e = Event(med, date, description)
                                    prescription = Prescription(name, description, fecha, take, person['name_person'],
                                                                person['id_remote'])
                                    identity = fecha + " - " + med
                                    scheduler.add_job(prescription_reminder, 'interval', days=1, start_date=date,
                                                      id=identity,
                                                      args=['default', prescription], max_instances=10000)
                                    logging.basicConfig()
                                    # insertion prescription
                                    insert_prescription(prescription)

                        file_procesed = True

                        if not check_internet_connection():
                            wifiConnection = datastore['wifiConnection']
                            if not alreadyRegistered(wifiConnection['ssid'], wifiConnection['psk']):
                                appendNewWifi(wifiConnection['ssid'], wifiConnection['psk'])

                    except ValueError:
                        print("JSON format failed")
                        os.system(
                            'rm /bluetooth/full_information.txt')
                        say('default',
                            u"Ha habido un error al sincronizar. Prueba a reenviar el fichero.")

                if file_procesed is True:
                    os.system('mv /bluetooth/full_information.txt /var/lib/snips/skills/ManuJazz.ACHOSintex/old_content.txt')
                    with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
                        content = "[Trying... sync done announce]"
                        text_file.write(content)
                    say('default',
                        u"Sincronización detectada. Ahora las prescripciones y los medicamentos se han actualizado.")
                    with open("/var/lib/snips/skills/ManuJazz.ACHOSintex/monitoring_output.txt", "a") as text_file:
                        content = "[Done... sync done announce]\n"
                        text_file.write(content)
                    disconnect_database()
            time.sleep(1)


def appendNewWifi(ssid, psk):
    quotes = "\""
    scape = "\\"
    os.system(
        "echo \"network={ \n ssid=" + scape + quotes + ssid + scape + quotes + " \n psk=" + scape + quotes + psk + scape + quotes + "\n}\" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf")


def alreadyRegistered(ssid, psk):
    datafile = file('/etc/wpa_supplicant/wpa_supplicant.conf')
    found = False
    for line in datafile:
        if ssid in line or psk in line:
            found = True
            break
    return found

def subscribe_taken_medicine(hermes, intentMessage):
    global global_prescription
    print("\nAffirmative answer!\n")
    if global_prescription is not None:
        print("\nWith global prescription!\n")
        if global_prescription.notices != 3 and global_prescription.notices != 0:
            print("\nDeleting other jobs\n")
            # back reminder is deleted
            identity = global_prescription.medicine
            backReminder.remove_job(identity)

        print("\nRegistering answer\n")
        # medicine take is registered
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d")
        take = Taken(global_prescription.medicine, dt_string, global_prescription.takes, "1",
                     global_prescription.id_user_remote)
        insert_taken(take)
        print("\nLocal inserted\n")
        # set parameters to cero
        global_prescription.notices = 0
        global_prescription = None

        mqttClient.publish_end_session(intentMessage.session_id, 'Perfecto. Me lo apunto')

        if check_internet_connection() and take.id_user_remote != -1:
            print("\nTrying remote connection\n")
            connect_remote_database()
            insert_remote_taken(take)
            print("\nRemotely inserted\n")
    else:
        print("\nNo global_prescription!\n")


def subscribe_not_taken_medicine(hermes, intentMessage):
    print("\nNegative answer!\n")
    if global_prescription is not None:
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d")
        take = Taken(global_prescription.medicine, dt_string, global_prescription.takes, "0",
                     global_prescription.id_user_remote)
        insert_taken(take)

        mqttClient.publish_end_session(intentMessage.session_id, u'De acuerdo. Te lo recordaré dentro de un momento')

        if check_internet_connection() and take.id_user_remote != -1:
            connect_remote_database()
            insert_remote_taken(take)

def subscribe_internet_connection(hermes, intentMessage):
    print("\nInternet checking\n")
    if check_internet_connection():
        mqttClient.publish_end_session(intentMessage.session_id, u'¡Sí! Estoy conectado a la red')
    else:
        mqttClient.publish_end_session(intentMessage.session_id, u'Ahora mismo no tengo conexión a internet. Prueba a especificar la red wifi desde la aplicación y sincronízame.')


if __name__ == "__main__":
    # os.system('sudo obexpushd -B -o /bluetooth -n &') # uncomment for bluetooth activation if first attempt fails
    # to add in /etc/rc.local -> echo -e "discoverable on \nquit" | sudo bluetoothctl
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
            .subscribe_intent("ManuJazz:Internet_connection", subscribe_internet_connection) \
            .start()
        print("out")
