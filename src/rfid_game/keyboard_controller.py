import logging
import time
from typing import Optional
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

logger = logging.getLogger(__name__)


class KeyboardController:
    def __init__(self):
        self.controller = keyboard.Controller()
        self._active = False

    def press_key(self, key: str):
        try:
            if len(key) == 1:
                self.controller.press(key)
                self.controller.release(key)
                logger.debug(f"Pressed key: {key}")
            else:
                special_key = getattr(Key, key.lower(), None)
                if special_key:
                    self.controller.press(special_key)
                    self.controller.release(special_key)
                    logger.debug(f"Pressed special key: {key}")
        except Exception as e:
            logger.error(f"Failed to press key '{key}': {e}")

    def hold_key(self, key: str, duration: float = 0.5):
        try:
            if len(key) == 1:
                self.controller.press(key)
                time.sleep(duration)
                self.controller.release(key)
                logger.debug(f"Held key: {key} for {duration}s")
        except Exception as e:
            logger.error(f"Failed to hold key '{key}': {e}")

    def type_text(self, text: str, delay: float = 0.05):
        try:
            for char in text:
                self.controller.press(char)
                self.controller.release(char)
                time.sleep(delay)
            logger.debug(f"Typed text: {text}")
        except Exception as e:
            logger.error(f"Failed to type text: {e}")

    def send_hotkey(self, *keys):
        try:
            for key in keys:
                if isinstance(key, str) and len(key) == 1:
                    self.controller.press(key)
                elif isinstance(key, Key):
                    self.controller.press(key)
            for key in reversed(keys):
                if isinstance(key, str) and len(key) == 1:
                    self.controller.release(key)
                elif isinstance(key, Key):
                    self.controller.release(key)
            logger.debug(f"Sent hotkey: {keys}")
        except Exception as e:
            logger.error(f"Failed to send hotkey: {e}")
