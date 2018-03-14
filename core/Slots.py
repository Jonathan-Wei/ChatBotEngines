#-*- coding=utf-8 -*-

import logging
logger = logging.getLogger(__name__)

class Slot():

    def __init__(self, type_name, name, initial_value=None, value_reset_delay=None,ask = None):
        self.type_name = type_name
        self.name = name
        self.value = initial_value
        self.initial_value = initial_value
        self._value_reset_delay = value_reset_delay
        self._ask = ask


