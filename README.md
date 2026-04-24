# rfid-game @ 0.2.0

## Requirements
- Python 3.8+ (inclui 3.14+)
- sllurp (LLRP protocol - pure Python)
- pynput

## Installation
```bash
pip install sllurp pynput
```

## Usage
```bash
python src/main.py
```

## CLI Commands

| Command | Description |
|---------|-------------|
| 1 | Scan tags for 10 seconds |
| 2 | List all scanned tags with stats |
| 3 | Register a keybind (tag -> key) |
| 4 | List all keybinds |
| 5 | Remove a keybind |
| 6 | Configure reader IP |
| 7 | Configure reader distance (transmit power) |
| 8 | Clear all scanned tags |
| 9 | Start game mode |
| 0 | Exit |

## How to Use

1. Run `python src/main.py`
2. Press `1` to scan tags and see what tags the reader detects
3. Press `2` to see all scanned tags with RSSI and count
4. Press `3` to register a keybind - pass a tag or type its EPC, then choose a key
5. Press `9` to start game mode - passing registered tags will send the mapped keys

## Reader Distance

Control how far the reader detects tags by adjusting transmit power (option 7):

| Preset | Power | Range |
|--------|-------|-------|
| Curta | 15dBm | ~0.5m |
| Media | 25dBm | ~1-3m |
| Longa | 30dBm | ~3-10m (max) |

You can also specify a custom value between 10-31dBm.
Changes require a program restart to take effect.

## Clear Scanned Tags

Use option 8 to clear all scanned tags from memory. This is useful when you want to start a fresh scan.

## Supported Keys

- Normal keys: a-z, 0-9, symbols
- Special keys: left, right, up, down, enter, tab, space, esc, backspace, delete, home, end, page_up, page_down, f1-f12

## Configuration

Keybinds and settings are saved to `src/rfid_game/config.json` automatically.

## Reader IP

Default IP: `192.168.89.25` (port 5084). Change via option 6 in the menu.

## Troubleshooting

- **"Leitor em uso"**: Only one client can connect to the reader at a time. Close other programs or restart the reader.
- **"Leitor em estado inconsistente"**: The reader needs a power cycle (unplug/replug).
- **No tags detected**: Check that tags are within range. Try option 7 to increase distance.
