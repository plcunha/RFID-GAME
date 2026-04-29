#!/usr/bin/env python3
"""
Test script for main.py options 3 (register keybind) and 9 (start game).
Uses mocking to simulate interactive input.
"""

import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rfid_game.cli import RFIDGameCLI, load_config, save_config
from rfid_game.game_logic import GameLogic


class TestOption3RegisterKeybind(unittest.TestCase):
    """Test option 3 - Register keybind functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use a test config to avoid modifying the real one
        self.test_config = {
            "keybinds": {},
            "scanned_tags": {},
            "reader_ip": "192.168.89.92",
            "tx_power_dbm": 30,
        }
        # Mock the config file operations
        self.config_patcher = patch(
            "rfid_game.cli.load_config", return_value=self.test_config
        )
        self.mock_load_config = self.config_patcher.start()

        self.save_patcher = patch("rfid_game.cli.save_config")
        self.mock_save_config = self.save_patcher.start()

        # Mock RFID reader to avoid actual connection
        self.reader_patcher = patch("rfid_game.cli.RFIDReader")
        self.mock_reader_class = self.reader_patcher.start()
        self.mock_reader = MagicMock()
        self.mock_reader.connected = False
        self.mock_reader_class.return_value = self.mock_reader

        # Mock KeyboardController
        self.kb_patcher = patch("rfid_game.cli.KeyboardController")
        self.mock_kb_class = self.kb_patcher.start()

        # Create CLI instance
        self.cli = RFIDGameCLI()

    def tearDown(self):
        """Clean up patches."""
        patch.stopall()

    def test_register_keybind_manual_epc(self):
        """Test registering a keybind with manual EPC input."""
        # Simulate user inputs: EPC -> key -> (returns from input)
        mock_inputs = ["e20000194104014617018d11", "space", ""]

        with patch("builtins.input", side_effect=mock_inputs):
            self.cli.register_keybind()

        # Verify keybind was registered
        self.assertIn("e20000194104014617018d11", self.cli.keybinds)
        self.assertEqual(self.cli.keybinds["e20000194104014617018d11"], "space")

        # Verify game_logic was synced
        self.assertIn("e20000194104014617018d11", self.cli.game_logic.tag_mappings)

    def test_register_keybind_cancel(self):
        """Test canceling keybind registration."""
        # Simulate user canceling: empty EPC, then empty manual EPC, then ENTER to go back
        # (scanner is not connected in this test)
        with patch("builtins.input", side_effect=["", "", ""]):
            self.cli.register_keybind()

        # Verify no keybinds were added
        self.assertEqual(len(self.cli.keybinds), 0)


class TestOption9StartGame(unittest.TestCase):
    """Test option 9 - Start game functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            "keybinds": {"e20000194104014617018d11": "space"},
            "scanned_tags": {},
            "reader_ip": "192.168.89.92",
            "tx_power_dbm": 30,
        }

        self.config_patcher = patch(
            "rfid_game.cli.load_config", return_value=self.test_config
        )
        self.mock_load_config = self.config_patcher.start()

        self.save_patcher = patch("rfid_game.cli.save_config")
        self.mock_save_config = self.save_patcher.start()

        # Mock RFID reader
        self.reader_patcher = patch("rfid_game.cli.RFIDReader")
        self.mock_reader_class = self.reader_patcher.start()
        self.mock_reader = MagicMock()
        self.mock_reader.connected = True
        self.mock_reader_class.return_value = self.mock_reader

        # Mock KeyboardController
        self.kb_patcher = patch("rfid_game.cli.KeyboardController")
        self.mock_kb_class = self.kb_patcher.start()

        self.cli = RFIDGameCLI()

    def tearDown(self):
        """Clean up patches."""
        patch.stopall()

    def test_start_game_with_keybinds(self):
        """Test that start_game sets _game_mode correctly."""
        # Mock time.sleep to avoid actual waiting
        with patch("time.sleep"):
            # Simulate KeyboardInterrupt to exit game loop
            with patch("time.sleep", side_effect=KeyboardInterrupt):
                self.cli.start_game()

        # Verify game mode was set and then cleared
        self.assertFalse(self.cli._game_mode)

    def test_start_game_no_keybinds(self):
        """Test that start_game requires keybinds."""
        self.cli.keybinds = {}
        self.cli.game_logic.tag_mappings = {}

        # Capture print output
        with patch("builtins.input", return_value=""):
            self.cli.start_game()

        # _game_mode should not have been set to True
        self.assertFalse(self.cli._game_mode)

    def test_start_game_no_reader(self):
        """Test that start_game requires reader connection."""
        self.cli.scanner.connected = False

        with patch("builtins.input", return_value=""):
            self.cli.start_game()

        self.assertFalse(self.cli._game_mode)


class TestIntegrationRFIDGameCLI(unittest.TestCase):
    """Integration tests for RFIDGameCLI."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            "keybinds": {},
            "scanned_tags": {},
            "reader_ip": "192.168.89.92",
            "tx_power_dbm": 30,
        }

        self.config_patcher = patch(
            "rfid_game.cli.load_config", return_value=self.test_config
        )
        self.mock_load_config = self.config_patcher.start()

        self.save_patcher = patch("rfid_game.cli.save_config")
        self.mock_save_config = self.save_patcher.start()

        self.reader_patcher = patch("rfid_game.cli.RFIDReader")
        self.mock_reader_class = self.reader_patcher.start()
        self.mock_reader = MagicMock()
        self.mock_reader.connected = True
        self.mock_reader_class.return_value = self.mock_reader

        self.kb_patcher = patch("rfid_game.cli.KeyboardController")
        self.mock_kb_class = self.kb_patcher.start()

        self.cli = RFIDGameCLI()

    def tearDown(self):
        """Clean up patches."""
        patch.stopall()

    def test_tag_detection_in_game_mode(self):
        """Test that tags are processed in game mode."""
        # Setup keybind
        test_epc = "e20000194104014617018d11"
        test_key = "space"
        self.cli.keybinds[test_epc] = test_key
        self.cli.game_logic.register_tag(test_epc, test_key)

        # Enable game mode
        self.cli._game_mode = True

        # Simulate tag detection
        with patch.object(self.cli.game_logic, "trigger_action") as mock_trigger:
            self.cli.on_tag_detected(test_epc, -50, 1)
            mock_trigger.assert_called_once_with(test_epc)

    def test_tag_detection_not_in_game_mode(self):
        """Test that tags are stored but not triggering actions when not in game mode."""
        test_epc = "e20000194104014617018d11"

        # Game mode off
        self.cli._game_mode = False

        with patch.object(self.cli.game_logic, "trigger_action") as mock_trigger:
            self.cli.on_tag_detected(test_epc, -50, 1)
            mock_trigger.assert_not_called()

        # Verify tag was stored
        tags = self.cli.tag_store.get_all_tags()
        self.assertEqual(len(tags), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
