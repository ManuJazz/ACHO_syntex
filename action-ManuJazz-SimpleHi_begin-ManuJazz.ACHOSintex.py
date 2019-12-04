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

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

mariadb_connection = None
cursor = None


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
    hour_string = now.strftime("%HH:%MM")
    query = "INSERT INTO Interaction(message, date, hour) VALUES (%s, %s, %s)"
    args = (_interaction, dt_string, hour_string)
    cursor.execute(query, args)
    mariadb_connection.commit()


def subscribe_answer_hi(hermes, intentMessage):
    connect_database()
    answer = intentMessage.input
    insert_interaction(answer)
    insert_mood(answer)
    mqttClient.publish_end_session(intentMessage.session_id, u'¡Tomo nota! Avísame si necesitas algo.')


def subscribe_simple_hi(hermes, intentMessage):
    connect_database()
    insert_interaction(intentMessage.input)
    mqttClient.publish_end_session(intentMessage.session_id, u'Hola. ¿Qué tal estás?')
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
