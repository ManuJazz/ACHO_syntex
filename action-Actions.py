{\rtf1\ansi\ansicpg1252\cocoartf1671\cocoasubrtf500
{\fonttbl\f0\fnil\fcharset0 Menlo-Regular;}
{\colortbl;\red255\green255\blue255;\red0\green0\blue0;}
{\*\expandedcolortbl;;\csgray\c0;}
\paperw11900\paperh16840\margl1440\margr1440\vieww18060\viewh16580\viewkind0
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\pardirnatural\partightenfactor0

\f0\fs22 \cf2 \CocoaLigature0 # -*- coding: utf-8 -*-\
import configparser\
from hermes_python.hermes import Hermes\
from hermes_python.ffi.utils import MqttOptions\
from hermes_python.ontology import *\
import io\
import os\
import json\
\
from apscheduler.schedulers.background import BackgroundScheduler\
from datetime import datetime\
import logging\
\
CONFIGURATION_ENCODING_FORMAT = "utf-8"\
CONFIG_INI = "config.ini"\
\
class SnipsConfigParser(configparser.SafeConfigParser):\
    def to_dict(self):\
        return \{section : \{option_name : option for option_name, option in self.items(section)\} for section in self.sections()\}\
\
\
def read_configuration_file(configuration_file):\
    try:\
        with io.open(configuration_file, encoding=CONFIGURATION_ENCODING_FORMAT) as f:\
            conf_parser = SnipsConfigParser()\
            conf_parser.readfp(f)\
            return conf_parser.to_dict()\
    except (IOError, configparser.Error) as e:\
        return dict()\
\
def subscribe_intent_callback(hermes, intentMessage):\
    conf = read_configuration_file(CONFIG_INI)\
    action_wrapper(hermes, intentMessage, conf)\
\
\
def action_wrapper(hermes, intentMessage, conf):\
    """ Write the body of the function that will be executed once the intent is recognized. \
    In your scope, you have the following objects : \
    - intentMessage : an object that represents the recognized intent\
    - hermes : an object with methods to communicate with the MQTT bus following the hermes protocol. \
    - conf : a dictionary that holds the skills parameters you defined. \
      To access global parameters use conf['global']['parameterName']. For end-user parameters use conf['secret']['parameterName'] \
     \
    Refer to the documentation for further details. \
    """ \
    result_sentence = "Activando Bluetooth para sincronizaci\'f3n"\
    current_session_id = intentMessage.session_id\
    hermes.publish_end_session(current_session_id, result_sentence)\
    os.system('obexpushd -B -o /bluetooth -n')\
\
def say(intentMessage, text):\
    mqttClient.publish_start_session_notification(intentMessage, text, None)\
\
def recordatorio(intentMessage, e):\
    print("Evento detectado para: %s" % datetime.now())\
    say(intentMessage, "Evento de medicamento detectado. A esta hora debes tomar "+e.med+". "+e.description)\
\
class Event(object):\
    def __init__(self, med, fecha, description):\
        self.med = med\
        self.fecha = fecha\
        self.description = description\
\
if __name__ == "__main__":\
    mqtt_opts = MqttOptions()\
    scheduler = BackgroundScheduler(\{'apscheduler.timezone': 'Europe/Madrid'\})\
    scheduler.start()\
    print("Main")\
\
	#file reading\
    filename="/bluetooth/full_information.json"\
    with open(filename, 'r') as f:\
    	datastore = json.load(f)\
\
	#obtains full info from file\
    for data in datastore:\
    	name = data['medicine']\
    	description = data['description']\
\
    	for take in data['takes']:\
        	print(name)\
        	print(description)\
		print(take)\
		fecha = "2019-07-09 "+ take\
		date=datetime.strptime(fecha,"%Y-%m-%d %H:%M:%S")\
		med = name\
		e = Event(med, date, description)\
		scheduler.add_job(recordatorio, 'date', run_date=date,id=fecha,args=['default',e], max_instances=10000)\
		logging.basicConfig()\
\
\
    os.system('mv /bluetooth/full_information.json ./old_content')\
    with Hermes(mqtt_options=mqtt_opts) as h, Hermes(mqtt_options=mqtt_opts) as mqttClient:\
        h.subscribe_intent("ManuJazz:Syncronize", subscribe_intent_callback) \\\
         .start()}