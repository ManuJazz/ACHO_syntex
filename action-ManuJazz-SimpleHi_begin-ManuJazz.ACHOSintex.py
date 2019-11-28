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


def subscribe_answer_hi(hermes, intentMessage):
    mqttClient.publish_end_session(intentMessage.session_id, 'Me alegra oir eso')


def subscribe_simple_hi(hermes, intentMessage):
    mqttClient.publish_end_session(intentMessage.session_id, u'Hola. ¿Qué tal estás?')
    mqttClient.publish_start_session_action(site_id=intentMessage.session_id, session_init_text=u'Hola. ¿Qué tal estás?',
                                            session_init_intent_filter=["ManuJazz:SimpleHi_answer"],
                                            session_init_can_be_enqueued=True,
                                            session_init_send_intent_not_recognized=True, custom_data=None)



if __name__ == "__main__":
    mqtt_opts = MqttOptions()
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:
        h.subscribe_intent("ManuJazz:SimpleHi_begin", subscribe_simple_hi) \
            .subscribe_intent("ManuJazz:SimpleHi_answer", subscribe_answer_hi) \
            .start()
