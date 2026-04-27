import logging
import time
from typing import Callable, List, Optional

from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, LLRP_DEFAULT_PORT

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def find_tx_power_index(tx_power_table: List[float], target_dbm: float) -> int:
    """Find the closest power index in the reader's power table."""
    best_idx = 0
    best_diff = float("inf")
    for i, val in enumerate(tx_power_table):
        diff = abs(val - target_dbm)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx


class RFIDReader:
    def __init__(
        self, ip: str, port: int = LLRP_DEFAULT_PORT, tx_power_dbm: float = 30
    ):
        self.ip = ip
        self.port = port
        self.tx_power_dbm = tx_power_dbm
        self.reader: Optional[LLRPReaderClient] = None
        self.connected = False
        self._callback: Optional[Callable] = None

    def connect(self) -> bool:
        try:
            # Build base config
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
            }

            # First, connect with default power to get power table from reader
            temp_config = LLRPReaderConfig({**config_dict, "tx_power": {1: 0}})
            self.reader = LLRPReaderClient(self.ip, self.port, temp_config)
            self.reader.add_tag_report_callback(self._on_tag_report)
            self.reader.connect()

            # Get power table from reader capabilities
            power_table = getattr(self.reader, "tx_power_table", None)
            if power_table:
                power_index = find_tx_power_index(power_table, self.tx_power_dbm)
                logger.info(
                    f"Setting tx_power to {self.tx_power_dbm}dBm (index {power_index})"
                )
                # Disconnect and reconnect with correct power
                self.reader.disconnect()
                self.reader = None

                # Reconnect with correct power setting
                config = LLRPReaderConfig({**config_dict, "tx_power": {1: power_index}})
                self.reader = LLRPReaderClient(self.ip, self.port, config)
                self.reader.add_tag_report_callback(self._on_tag_report)
                self.reader.connect()
            else:
                logger.warning(
                    "Could not get power table from reader, using default power"
                )

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
            elif "ROSpec" in error_msg or "already configured" in error_msg.lower():
                logger.error(
                    "Reader in inconsistent state. "
                    "Restart the reader (power cycle) and try again."
                )
            else:
                logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        if self.reader and self.connected:
            try:
                self.reader.disconnect()
            except Exception:
                try:
                    self.reader.hard_disconnect()
                except Exception:
                    pass
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
