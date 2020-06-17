#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import configparser
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import io
import time
import mysql.connector as mariadb
from datetime import datetime, timedelta, date

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

mariadb_connection = None
cursor = None


def connect_database():
    global mariadb_connection
    global cursor
    mariadb_connection = mariadb.connect(host='localhost', user='root', password='', database='AchoSintex',
                                         connection_timeout=20)
    cursor = mariadb_connection.cursor()


def get_taken_pills():
    global mariadb_connection
    global cursor
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d")
    query = "SELECT * FROM Taken WHERE taken = '1' AND day = %s"
    args = (dt_string,)
    rows_count = cursor.execute(query, args)
    rows = cursor.fetchall()
    if cursor.rowcount > 0:
        return rows
    else:
        return None


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


def subscribe_intent_callback(hermes, intentMessage):
    conf = read_configuration_file(CONFIG_INI)
    action_wrapper(hermes, intentMessage, conf)


def action_wrapper(hermes, intentMessage, conf):
    """ Write the body of the function that will be executed once the intent is recognized. 
    In your scope, you have the following objects : 
    - intentMessage : an object that represents the recognized intent
    - hermes : an object with methods to communicate with the MQTT bus following the hermes protocol. 
    - conf : a dictionary that holds the skills parameters you defined. 
      To access global parameters use conf['global']['parameterName']. For end-user parameters use conf['secret']['parameterName'] 
     
    Refer to the documentation for further details. 
    """
    connect_database()
    insert_interaction(intentMessage.input)
    print("TakenPills_query")
    rows = get_taken_pills()
    sentence = u"Según lo que tengo registrado, hoy has tomado: "
    medicine = ""
    if rows is not None:
        for take in rows:
            medicine = medicine + take[1] + " a las " + take[2] + ", "
        message = sentence + medicine
    else:
        message = u"Todavía no has tomado ninguna medicina"
    mqttClient.publish_end_session(intentMessage.session_id, message)

def subscribe_pendentPills(hermes, intentMessage):
    # action

if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        h \
        .subscribe_intent("ManuJazz:TakenPills_query", subscribe_intent_callback) \
        .subscribe_intent("ManuJazz:PendentPills_query", subscribe_pendentPills) \
            .start()
