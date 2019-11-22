#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# encoding: utf-8

import configparser
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import io

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

class SnipsConfigParser(configparser.SafeConfigParser):
    def to_dict(self):
        return {section : {option_name : option for option_name, option in self.items(section)} for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding=CONFIGURATION_ENCODING_FORMAT) as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, configparser.Error) as e:
        return dict()

def subscribe_answer_hi(hermes, intentMessage):
    conf = read_configuration_file(CONFIG_INI)
    process_response(hermes, intentMessage, conf)

def subscribe_simple_hi(hermes, intentMessage):
    conf = read_configuration_file(CONFIG_INI)
    ask_how_feel(hermes, intentMessage, conf)

def process_response(hermes, intentMessage, conf):
    mqttClient.publish_start_session_notification('default', 'Me alegra oir eso', None)
    mqttClient.publish_end_session('default', "")

def ask_how_feel(hermes, intentMessage, conf):
    """ Write the body of the function that will be executed once the intent is recognized. 
    In your scope, you have the following objects : 
    - intentMessage : an object that represents the recognized intent
    - hermes : an object with methods to communicate with the MQTT bus following the hermes protocol. 
    - conf : a dictionary that holds the skills parameters you defined. 
      To access global parameters use conf['global']['parameterName']. For end-user parameters use conf['secret']['parameterName'] 
    Refer to the documentation for further details. 
    """
    #mqttClient.publish_start_session_notification('Default', "Hola. ¿Qué tal estás?", None)
    mqttClient.publish_start_session_action(site_id='default', session_init_text = u'Hola. ¿Qué tal estás?', session_init_intent_filter = ["ManuJazz:SimpleHi_answer"], session_init_can_be_enqueued=True, session_init_send_intent_not_recognized=True, custom_data=None)


if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        h.subscribe_intent("ManuJazz:SimpleHi_begin", subscribe_simple_hi) \
	.subscribe_intent("ManuJazz:SimpleHi_answer", subscribe_answer_hi) \
         .start()
