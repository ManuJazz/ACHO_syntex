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

# database connection
mariadb_connection = mariadb.connect(user='root', password='', database='AchoSintex')
cursor = mariadb_connection.cursor()


def get_taken_pills():
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d")
    query = "SELECT * FROM Taken WHERE taken = '1' AND day = %s"
    args = (dt_string, )
    cursor.execute(query, args)
    rows = cursor.fetchall()
    return rows


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
    rows = get_taken_pills()
    sentence = u"Según lo que tengo registrado, hoy has tomado: "
    medicine = ""
    for take in rows:
        medicine = medicine + take[1] + " a las "+take[2]+", "
    mqttClient.publish_end_session(intentMessage.session_id, sentence + medicine)


if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        h.subscribe_intent("ManuJazz:Taken_request", subscribe_intent_callback) \
            .start()
