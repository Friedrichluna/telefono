#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time

from .button import Button
from .CONSTANTS import BUTTON_DELAY

class InvButton:
    def __init__(self, *args, **kwargs):
        self._button = Button(*args, **kwargs)

    @property
    def value(self):
        return not self._button.value

    @property
    def is_pressed(self):
        return not self._button.is_pressed

    @property
    def is_released (self):
        if not self.is_pressed:
            return False

        while self.is_pressed:
            time.sleep (BUTTON_DELAY)

        return True

    def close(self):
        self._button.close()
