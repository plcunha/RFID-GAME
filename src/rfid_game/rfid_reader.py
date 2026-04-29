import logging
import time
from typing import Callable, Optional

from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, LLRP_DEFAULT_PORT

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RFIDReader:
    def __init__(
        self,
        ip: str,
        port: int = LLRP_DEFAULT_PORT,
        tx_power_dbm: float = 30,
        callback: Optional[Callable] = None,
    ):
        self.ip = ip
        self.port = port
        self.tx_power_dbm = tx_power_dbm
        self.reader: Optional[LLRPReaderClient] = None
        self.connected = False
        self._callback: Optional[Callable] = callback

    def _build_config(self):
        """Build LLRPReaderConfig."""
        config_dict = {
            "tag_content_selector": {
                "EnableROSpecID": False,
                "EnableSpecIndex": False,
                "EnableInventoryParameterSpecID": False,
                "EnableAntennaID": True,
                "EnableChannelIndex": False,
                "EnablePeakRSSI": True,
                "EnableFirstSeenTimestamp": False,
                "EnableLastSeenTimestamp": False,
                "EnableTagSeenCount": False,
                "EnableAccessSpecID": False,
            },
            # Configure immediate tag reporting (disable batching)
            # report_every_n_tags=1: report after each tag
            # report_timeout_ms=0: no timeout delay
            "report_every_n_tags": 1,
            "report_timeout_ms": 0,
        }
        config = LLRPReaderConfig(config_dict)
        # sllurp v3.0.5 expects tx_power as dict {antenna_id: power_index}
        # Set power index 30 for antenna 1 (typical max power for Impinj readers)
        # Power index 30 typically corresponds to ~30 dBm (depending on reader model)
        config.tx_power = {1: 30}
        return config

    def connect(self) -> bool:
        try:
            config = self._build_config()
            self.reader = LLRPReaderClient(self.ip, self.port, config)
            self.reader.add_tag_report_callback(self._on_tag_report)
            self.reader.connect()
            self.connected = True
            logger.info(f"Connected to reader at {self.ip}:{self.port}")
            return True

        except Exception as e:
            error_msg = str(e)
            if "connection already exists" in error_msg.lower():
                logger.error(
                    "Reader already in use by another client. "
                    "Close other programs or restart the reader."
                )
            else:
                logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        if self.reader:
            try:
                self.reader.disconnect()
            except Exception:
                try:
                    self.reader.hard_disconnect()
                except Exception:
                    pass
        self.reader = None
        self.connected = False
        logger.info("Disconnected from reader")

    def set_callback(self, callback: Callable):
        self._callback = callback

    def _on_tag_report(self, reader, tag_reports):
        for tag in tag_reports:
            epc_raw = tag.get("EPC", b"")
            if isinstance(epc_raw, bytes):
                epc = epc_raw.hex()
            else:
                epc = str(epc_raw)
            rssi = tag.get("PeakRSSI", -100)
            antenna = tag.get("AntennaID", 0)
            if self._callback:
                self._callback(epc, rssi, antenna)

    def wait(self, timeout: Optional[float] = None):
        if self.connected and self.reader:
            self.reader.join(timeout)

    def is_alive(self) -> bool:
        return self.connected and self.reader is not None and self.reader.is_alive()

    def start(self):
        """Start the reader inventory (no-op, sllurp starts automatically)."""
        pass

    def stop(self):
        """Stop the reader inventory (no-op)."""
        pass
