#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# encoding: utf-8

import configparser
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import io
from datetime import datetime, timedelta, date
import mysql.connector as mariadb
import random

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

mariadb_connection = None
cursor = None
isAnswer = False
isChecking = False


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


def connect_database():
    global mariadb_connection
    global cursor
    mariadb_connection = mariadb.connect(host='localhost', user='root', password='', database='AchoSintex',
                                         connection_timeout=20)
    cursor = mariadb_connection.cursor()


def get_forgotten_pills():
    global mariadb_connection
    global cursor
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d")
    query = "SELECT * FROM Taken WHERE taken = '2' AND day = %s"
    args = (dt_string,)
    rows_count = cursor.execute(query, args)
    rows = cursor.fetchall()
    if cursor.rowcount > 0:
        return rows
    else:
        return None


def insert_mood(_mood):
    global mariadb_connection
    global cursor
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d")
    query = "INSERT INTO Mood(message, date) VALUES (%s, %s)"
    args = (_mood, dt_string)
    cursor.execute(query, args)
    mariadb_connection.commit()


def insert_interaction(_interaction):
    global mariadb_connection
    global cursor
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d")
    hour_string = now.strftime("%H:%M")
    query = "INSERT INTO Interaction(message, date, hour) VALUES (%s, %s, %s)"
    args = (_interaction, dt_string, hour_string)
    cursor.execute(query, args)
    mariadb_connection.commit()


def subscribe_answer_hi(hermes, intentMessage):
    global isAnswer
    if isAnswer is True:
        connect_database()
        answer = intentMessage.input
        # insert_interaction(answer)
        insert_mood(answer)
        isAnswer = False
        mqttClient.publish_end_session(intentMessage.session_id, u'¡Tomo nota! Avísame si necesitas algo.')


'''
def subscribe_affirmation(hermes, intentMessage):
    global isChecking
    if isChecking is True:
        mqttClient.publish_end_session(intentMessage.session_id, 'Vaya, la próxima vez hablaré más fuerte.')
        isChecking = False


def subscribe_negation(hermes, intentMessage):
    global isChecking
    if isChecking is True:
        mqttClient.publish_end_session(intentMessage.session_id,
                                   'Entiendo. Si sales de casa no olvides llevar tus pastillas.')
        isChecking = False
        
        
'''


def subscribe_simple_hi(hermes, intentMessage):
    connect_database()
    insert_interaction(intentMessage.input)
    global isAnswer
    global isChecking
    isAnswer = True

    prob_reminder = random.randint(0, 5)
    rows = get_forgotten_pills()
    if prob_reminder == 0 and rows is not None:
        isChecking = True
        mqttClient.publish_end_session(intentMessage.session_id,
                                       u'Hola. Antes te he avisado de una toma de pastillas pero no me has respondido. Si sales recuerda llevar tus pastillas contigo. Por cierto, ¿qué tal estás?')
        '''mqttClient.publish_start_session_action(site_id='default', session_init_text="",
                                            session_init_intent_filter=["ManuJazz:Affirmation", "ManuJazz:Negation"],
                                            session_init_can_be_enqueued=True,
                                            session_init_send_intent_not_recognized=True, custom_data=None)
        '''

    else:
        isChecking = False
        hi_message = ["Hola", "Buenas", u"¿Qué hay?"]
        prob_advice = random.randint(0, 2)
        advice = ""
        if prob_advice == 0:
            advices = [u"Recuerda beber abundante agua. Te mantendrá hidratado y tiene importantes beneficios",
                       u"¡Recuerda llevar una dieta equilibrada y saludable!",
                       u"¡Qué frío hace!"]
            advice = ". " + advices[random.randint(0, 2)]

        message = hi_message[random.randint(0, 2)] + advice + u'. ¿Qué tal estás?'
        mqttClient.publish_end_session(intentMessage.session_id, message)

    mqttClient.publish_start_session_action(site_id='default', session_init_text="",
                                            session_init_intent_filter=["ManuJazz:SimpleHi_answer"],
                                            session_init_can_be_enqueued=True,
                                            session_init_send_intent_not_recognized=True, custom_data=None)


if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        h.subscribe_intent("ManuJazz:SimpleHi_begin", subscribe_simple_hi) \
            .subscribe_intent("ManuJazz:SimpleHi_answer", subscribe_answer_hi) \
            .start()
        # .subscribe_intent("ManuJazz:Affirmation", subscribe_affirmation) \
        # .subscribe_intent("ManuJazz:Negation", subscribe_negation) \
