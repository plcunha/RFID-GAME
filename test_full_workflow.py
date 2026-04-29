#!/usr/bin/env python3
"""Test script to verify full RFID Game workflow after tx_power fix."""

import sys
import os
import time
import threading

# Add src to path - the rfid_game package is inside src/
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, src_path)

# Verify the path is correct
print(f"Python path includes: {src_path}")
print(f"rfid_game exists: {os.path.exists(os.path.join(src_path, 'rfid_game'))}")

from rfid_game.rfid_reader import RFIDReader
from rfid_game.cli import load_config, save_config
from rfid_game.game_logic import GameLogic


def test_tag_scanning():
    """Test 1: Verify tag scanning works with fixed tx_power config."""
    print("=" * 60)
    print("TEST 1: Tag Scanning")
    print("=" * 60)

    config = load_config()
    reader = RFIDReader(
        config.get("reader_ip", "192.168.89.92"),
        tx_power_dbm=config.get("tx_power_dbm", 30),
    )

    # Store tags for testing (thread-safe)
    scanned_tags = {}
    tags_lock = threading.Lock()
    # Event to signal when tags are detected
    tag_event = threading.Event()
    # Event to signal when done waiting
    done_event = threading.Event()

    def tag_callback(epc, rssi, antenna):
        with tags_lock:
            scanned_tags[epc] = {"epc": epc, "rssi": rssi, "antenna": antenna}
        print(f"  Tag detectada: EPC={epc}, RSSI={rssi}, Antenna={antenna}", flush=True)
        tag_event.set()  # Signal that we got at least one tag

    try:
        # Set callback BEFORE connecting
        reader.set_callback(tag_callback)
        print(f"\nConectando ao leitor em {config.get('reader_ip')}...")
        reader.connect()
        print("Conectado com sucesso!")

        # Give inventory time to start
        time.sleep(1)

        print("\nEscaneando tags por 15 segundos...")
        print("(Aproxime as tags do leitor RFID)")
        print("Aguardando deteccao de tags...")

        # Wait for tags with a timeout
        tag_detected = tag_event.wait(timeout=15)

        if tag_detected:
            with tags_lock:
                print(f"\n[OK] Tags detectadas: {len(scanned_tags)}")
                for epc, data in scanned_tags.items():
                    print(
                        f"  - EPC: {epc}, RSSI: {data['rssi']}, Antena: {data['antenna']}"
                    )

            # Save scanned tags to config for next tests
            config = load_config()
            if "scanned_tags" not in config:
                config["scanned_tags"] = {}
            with tags_lock:
                for epc, data in scanned_tags.items():
                    config["scanned_tags"][epc] = data
            save_config(config)
            print("[OK] Tags salvas no config.json para proximos testes.")
            return True
        else:
            print("\n[ERRO] Nenhuma tag detectada no tempo limite!")
            return False

    except Exception as e:
        print(f"\n[ERRO] Falha no teste de scanning: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        print("\nDesconectando leitor...")
        done_event.set()
        reader.disconnect()
        print("Desconectado.")


def test_keybind_registration():
    """Test 2: Verify keybind registration works."""
    print("\n" + "=" * 60)
    print("TEST 2: Keybind Registration")
    print("=" * 60)

    config = load_config()

    # Check if we have scanned tags to work with
    if not config.get("scanned_tags"):
        print("[ERRO] Nenhuma tag escaneada encontrada no config.json")
        print("Execute o TEST 1 primeiro para escanear tags.")
        return False

    # Get first scanned tag
    tags = list(config["scanned_tags"].values())
    if not tags:
        print("[ERRO] Nenhuma tag disponivel para teste.")
        return False

    test_tag = tags[0]["epc"]
    test_key = "t"  # Test with 't' key

    print(f"\nRegistrando keybind: tag {test_tag[-4:]} -> tecla '{test_key}'")

    # Register the keybind
    if "keybinds" not in config:
        config["keybinds"] = {}

    config["keybinds"][test_tag] = test_key
    save_config(config)

    # Verify it was saved
    updated_config = load_config()
    if test_tag in updated_config.get("keybinds", {}):
        print(f"[OK] Keybind registrado com sucesso!")
        print(f"  Tag: {test_tag[-4:]}, Tecla: {updated_config['keybinds'][test_tag]}")
        return True
    else:
        print("[ERRO] Falha ao registrar keybind!")
        return False


def test_game_mode():
    """Test 3: Verify game mode works with registered keybinds."""
    print("\n" + "=" * 60)
    print("TEST 3: Game Mode")
    print("=" * 60)

    config = load_config()

    # Check if we have keybinds registered
    if not config.get("keybinds"):
        print("[ERRO] Nenhum keybind registrado.")
        print("Execute o TEST 2 primeiro para registrar um keybind.")
        return False

    # Initialize game logic
    game = GameLogic(cooldown_seconds=0.5)

    # Load tag mappings from config (use tag_mappings, not keybinds!)
    keybinds = config.get("keybinds", {})
    print(f"\nCarregando {len(keybinds)} keybinds para o jogo...")

    for epc, key in keybinds.items():
        game.register_tag(epc, key)
        print(f"  Tag {epc[-4:]} -> acao '{key}'")

    # Verify mappings were registered - use tag_mappings (not keybinds!)
    if not game.tag_mappings:
        print("[ERRO] Nenhuma tag carregada no GameLogic!")
        return False

    print(f"[OK] GameLogic carregado com {len(game.tag_mappings)} mapeamentos")

    # Test tag trigger (simulate tag detection)
    test_epc = list(keybinds.keys())[0]
    test_action = keybinds[test_epc]

    print(f"\nTestando deteccao de tag: {test_epc[-4:]} -> '{test_action}'")

    triggered = [False]
    received_epc = [None]
    received_action = [None]

    def on_tag_action(epc, action):
        triggered[0] = True
        received_epc[0] = epc
        received_action[0] = action
        print(f"  [OK] Acao disparada: EPC={epc[-4:]}, Acao={action}")

    game.on_tag_detected(on_tag_action)
    game.trigger_action(test_epc)

    if (
        triggered[0]
        and received_epc[0] == test_epc
        and received_action[0] == test_action
    ):
        print("[OK] Game mode funcionando corretamente!")
        return True
    else:
        print("[ERRO] Falha no game mode!")
        return False


def test_reader_reconnect():
    """Test 4: Verify reader can reconnect after disconnect."""
    print("\n" + "=" * 60)
    print("TEST 4: Reader Reconnect")
    print("=" * 60)

    config = load_config()
    reader = RFIDReader(
        config.get("reader_ip", "192.168.89.92"),
        tx_power_dbm=config.get("tx_power_dbm", 30),
    )

    try:
        # Connect
        print("\nConectando...")
        reader.connect()
        print("[OK] Conectado.")

        # Disconnect
        print("Desconectando...")
        reader.disconnect()
        print("[OK] Desconectado.")

        # Reconnect
        print("Reconectando...")
        reader.connect()
        print("[OK] Reconectado com sucesso!")

        reader.disconnect()
        print("[OK] TEST 4 passou: Reconexao funciona.")
        return True

    except Exception as e:
        print(f"[ERRO] Falha no teste de reconexao: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        try:
            reader.disconnect()
        except:
            pass


def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# RFID GAME - Teste de Workflow Completo")
    print("#" * 60)

    results = []

    # Run tests
    results.append(("Tag Scanning", test_tag_scanning()))
    results.append(("Keybind Registration", test_keybind_registration()))
    results.append(("Game Mode", test_game_mode()))
    results.append(("Reader Reconnect", test_reader_reconnect()))

    # Summary
    print("\n" + "#" * 60)
    print("# RESUMO DOS TESTES")
    print("#" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "[OK]" if result else "[ERRO]"
        print(f"{status} {name}")
        if result:
            passed += 1
        else:
            failed += 1

    print("\n" + "-" * 60)
    print(f"Total: {passed + failed} | Passou: {passed} | Falhou: {failed}")
    print("-" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
