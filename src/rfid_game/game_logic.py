import logging
import time
from typing import Dict, Callable, Optional

logger = logging.getLogger(__name__)


class GameLogic:
    def __init__(self, cooldown_seconds: float = 0.5):
        self.tag_mappings: Dict[str, str] = {}
        self._on_tag_detected_callback: Optional[Callable[[str, str], None]] = None
        self._last_epc: Optional[str] = None
        self._last_trigger_time: float = 0.0
        self._cooldown_seconds = cooldown_seconds

    def register_tag(self, epc: str, action: str):
        epc_lower = epc.lower()
        self.tag_mappings[epc_lower] = action
        logger.info(f"Registered tag {epc_lower[:16]}... -> {action}")

    def unregister_tag(self, epc: str):
        epc_lower = epc.lower()
        if epc_lower in self.tag_mappings:
            del self.tag_mappings[epc_lower]
            logger.info(f"Unregistered tag {epc_lower[:16]}...")

    def get_action(self, epc: str) -> Optional[str]:
        epc_lower = epc.lower()
        return self.tag_mappings.get(epc_lower)

    def on_tag_detected(self, callback: Callable[[str, str], None]):
        self._on_tag_detected_callback = callback

    def trigger_action(self, epc: str):
        now = time.time()
        if (
            epc == self._last_epc
            and (now - self._last_trigger_time) < self._cooldown_seconds
        ):
            return

        self._last_epc = epc
        self._last_trigger_time = now

        action = self.get_action(epc)
        if action and self._on_tag_detected_callback:
            self._on_tag_detected_callback(epc, action)
