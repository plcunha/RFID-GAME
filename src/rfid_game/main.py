import logging
import time
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RFIDGameInterface:
    def __init__(self, reader_ip: str):
        from rfid_reader import RFIDReader
        from keyboard_controller import KeyboardController
        from game_logic import GameLogic

        self.rfid_reader = RFIDReader(reader_ip)
        self.keyboard = KeyboardController()
        self.game_logic = GameLogic()
        self.running = False

    def setup(self):
        logger.info("Setting up RFID Game Interface...")

        if not self.rfid_reader.connect():
            logger.error("Failed to connect to RFID reader")
            return False

        self.game_logic.on_tag_detected(self._execute_action)
        self.rfid_reader.set_callback(self._on_tag_detected)

        logger.info("Setup complete!")
        return True

    def _on_tag_detected(self, epc: str, rssi: int, antenna: int):
        logger.info(f"Tag detected: {epc} (RSSI: {rssi}, Antenna: {antenna})")
        self.game_logic.trigger_action(epc)

    def _execute_action(self, epc: str, action: str):
        logger.info(f"Executing action '{action}' for tag {epc[:16]}...")
        self.keyboard.press_key(action)

    def register_tag_action(self, epc: str, key: str):
        self.game_logic.register_tag(epc, key)

    def run(self):
        self.running = True
        logger.info("RFID Game Interface running. Press Ctrl+C to stop.")

        try:
            while self.running:
                self.rfid_reader.wait(timeout=1.0)
                if not self.rfid_reader.is_alive():
                    logger.error("Reader connection lost")
                    self.running = False
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logger.info("Stopping RFID Game Interface...")
        self.running = False
        self.rfid_reader.disconnect()
        logger.info("Stopped.")

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def main():
    READER_IP = "192.168.89.25"

    interface = RFIDGameInterface(READER_IP)

    if not interface.setup():
        logger.error("Failed to setup interface")
        sys.exit(1)

    interface.register_tag_action("e200001234567890", "left")
    interface.register_tag_action("e200001234567891", "right")
    interface.register_tag_action("e200001234567892", "up")
    interface.register_tag_action("e200001234567893", "down")

    interface.run()


if __name__ == "__main__":
    main()
