import logging
import time
import sys
import os
import json
import threading
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

SPECIAL_KEYS = [
    "left",
    "right",
    "up",
    "down",
    "enter",
    "tab",
    "space",
    "esc",
    "backspace",
    "delete",
    "home",
    "end",
    "page_up",
    "page_down",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
]


def decode_epc(epc_hex: str) -> str:
    try:
        return bytes.fromhex(epc_hex).decode("ascii", errors="replace")
    except (ValueError, UnicodeDecodeError):
        return epc_hex[:24]


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"keybinds": {}, "scanned_tags": {}, "reader_ip": "192.168.89.25"}


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


class TagStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._tags: Dict[str, dict] = {}

    def add_tag(self, epc: str, rssi: int, antenna: int):
        with self._lock:
            if epc not in self._tags:
                self._tags[epc] = {
                    "epc": epc,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "count": 1,
                    "avg_rssi": rssi,
                    "total_rssi": rssi,
                    "antennas": {antenna},
                }
            else:
                tag = self._tags[epc]
                tag["last_seen"] = time.time()
                tag["count"] += 1
                tag["total_rssi"] += rssi
                tag["avg_rssi"] = tag["total_rssi"] // tag["count"]
                tag["antennas"].add(antenna)

    def get_all_tags(self) -> List[dict]:
        with self._lock:
            result = []
            for tag in self._tags.values():
                result.append(
                    {
                        "epc": tag["epc"],
                        "first_seen": tag["first_seen"],
                        "last_seen": tag["last_seen"],
                        "count": tag["count"],
                        "avg_rssi": tag["avg_rssi"],
                        "antennas": sorted(tag["antennas"]),
                    }
                )
            return sorted(result, key=lambda t: t["count"], reverse=True)

    def get_tags_for_config(self) -> dict:
        with self._lock:
            return {
                epc: {
                    "first_seen": t["first_seen"],
                    "last_seen": t["last_seen"],
                    "count": t["count"],
                    "avg_rssi": t["avg_rssi"],
                    "antennas": sorted(t["antennas"]),
                }
                for epc, t in self._tags.items()
            }


class RFIDScanner:
    def __init__(self, reader_ip: str):
        from sllurp.llrp import LLRPReaderClient, LLRPReaderConfig, LLRP_DEFAULT_PORT

        self.LLRPReaderClient = LLRPReaderClient
        self.LLRPReaderConfig = LLRPReaderConfig
        self.LLRP_DEFAULT_PORT = LLRP_DEFAULT_PORT
        self.reader_ip = reader_ip
        self.reader = None
        self.connected = False
        self._callback = None

    def connect(self) -> bool:
        try:
            config = self.LLRPReaderConfig(
                {
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
                    }
                }
            )
            self.reader = self.LLRPReaderClient(
                self.reader_ip, self.LLRP_DEFAULT_PORT, config
            )
            self.reader.add_tag_report_callback(self._on_tag_report)
            self.reader.connect()
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to reader: {e}")
            return False

    def set_callback(self, callback):
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

    def start(self):
        pass

    def stop(self):
        pass

    def wait(self, timeout=1.0):
        if self.connected and self.reader:
            self.reader.join(timeout)

    def is_alive(self) -> bool:
        return self.connected and self.reader is not None and self.reader.is_alive()

    def disconnect(self):
        if self.reader and self.connected:
            self.reader.disconnect()
            self.connected = False


class GameKeyboard:
    def __init__(self):
        from pynput.keyboard import Key, Controller

        self.controller = Controller()
        self.Key = Key

    def press_key(self, key: str):
        try:
            if len(key) == 1:
                self.controller.press(key)
                self.controller.release(key)
            else:
                special_key = getattr(self.Key, key.lower(), None)
                if special_key:
                    self.controller.press(special_key)
                    self.controller.release(special_key)
        except Exception as e:
            logger.error(f"Failed to press key '{key}': {e}")


class RFIDGameCLI:
    def __init__(self):
        self.config = load_config()
        self.keybinds: Dict[str, str] = self.config.get("keybinds", {})
        self.tag_store = TagStore()
        self.scanner: Optional[RFIDScanner] = None
        self.keyboard = GameKeyboard()
        self.running = False
        self._game_mode = False

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def print_header(self, title: str):
        print("=" * 60)
        print(f"  RFID GAME - {title}")
        print("=" * 60)

    def print_menu(self):
        self.clear_screen()
        self.print_header("MENU PRINCIPAL")
        reader_ip = self.config.get("reader_ip", "192.168.89.25")
        print(f"\n  Leitor: {reader_ip}")
        print(f"  Keybinds: {len(self.keybinds)}")
        print(f"  Tags escaneadas: {len(self.tag_store.get_all_tags())}")
        print()
        print("  1. ESCANEAR TAGS")
        print("  2. LISTAR TAGS ESCANEADAS")
        print("  3. CADASTRAR KEYBIND")
        print("  4. LISTAR KEYBINDS")
        print("  5. REMOVER KEYBIND")
        print("  6. CONFIGURAR IP DO LEITOR")
        print("  7. INICIAR JOGO")
        print()
        print("  0. SAIR")
        print()

    def on_tag_detected(self, epc: str, rssi: int, antenna: int):
        self.tag_store.add_tag(epc, rssi, antenna)
        if self._game_mode:
            key = self.keybinds.get(epc)
            if key:
                self.keyboard.press_key(key)

    def connect_reader(self) -> bool:
        reader_ip = self.config.get("reader_ip", "192.168.89.25")
        print(f"\nConectando ao leitor em {reader_ip}...")
        self.scanner = RFIDScanner(reader_ip)
        if self.scanner.connect():
            self.scanner.set_callback(self.on_tag_detected)
            self.scanner.start()
            print("Conectado com sucesso!")
            return True
        else:
            print("Falha ao conectar ao leitor.")
            return False

    def disconnect_reader(self):
        if self.scanner:
            self.scanner.stop()
            self.scanner.disconnect()
            self.scanner = None

    def scan_tags(self):
        if not self.scanner or not self.scanner.connected:
            if not self.connect_reader():
                input("\nPressione ENTER para voltar...")
                return

        self.clear_screen()
        self.print_header("ESCANEAR TAGS")
        print("\nLendo tags... Pressione Ctrl+C para parar.\n")
        print(f"{'EPC':<26} {'RSSI':<8} {'Antena':<8} {'Vezes':<8}")
        print("-" * 60)

        last_count = 0
        try:
            while True:
                tags = self.tag_store.get_all_tags()
                if len(tags) != last_count:
                    self.clear_screen()
                    self.print_header("ESCANEAR TAGS")
                    print("\nLendo tags... Pressione Ctrl+C para parar.\n")
                    print(f"{'EPC':<26} {'RSSI':<8} {'Antena':<8} {'Vezes':<8}")
                    print("-" * 60)
                    for tag in tags:
                        epc_display = decode_epc(tag["epc"])[:24]
                        antennas = ",".join(str(a) for a in tag["antennas"])
                        print(
                            f"{epc_display:<26} {tag['avg_rssi']:<8} {antennas:<8} {tag['count']:<8}"
                        )
                    print(f"\nTotal: {len(tags)} tag(s) unica(s)")
                    last_count = len(tags)
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    def list_scanned_tags(self):
        self.clear_screen()
        self.print_header("TAGS ESCANEADAS")

        tags = self.tag_store.get_all_tags()
        if not tags:
            print("\nNenhuma tag escaneada ainda.")
            print("Use a opcao 1 para escanear tags primeiro.")
        else:
            print(
                f"\n{'EPC':<26} {'RSSI':<8} {'Antena':<8} {'Vezes':<8} {'Ultima Vezida':<15}"
            )
            print("-" * 70)
            for tag in tags:
                last = time.strftime("%H:%M:%S", time.localtime(tag["last_seen"]))
                antennas = ",".join(str(a) for a in tag["antennas"])
                epc_display = decode_epc(tag["epc"])[:24]
                print(
                    f"{epc_display:<26} {tag['avg_rssi']:<8} {antennas:<8} {tag['count']:<8} {last:<15}"
                )

            print(f"\nTotal: {len(tags)} tag(s) escaneada(s)")

        input("\nPressione ENTER para voltar...")

    def register_keybind(self):
        if not self.scanner or not self.scanner.connected:
            if not self.connect_reader():
                input("\nPressione ENTER para voltar...")
                return

        self.clear_screen()
        self.print_header("CADASTRAR KEYBIND")
        print("\nPasse a tag RFID que deseja cadastrar...")
        print("Ou digite o EPC manualmente (Enter para cancelar).\n")

        choice = input("EPC da tag (ou deixe vazio para escanear): ").strip().lower()

        if choice == "":
            print("Aguardando leitura da tag...")
            epc = None
            start = time.time()
            while time.time() - start < 10:
                tags = self.tag_store.get_all_tags()
                if tags:
                    epc = tags[0]["epc"]
                    break
                time.sleep(0.2)
            if not epc:
                print("Nenhuma tag lida em 10 segundos.")
                input("Pressione ENTER para voltar...")
                return
            print(f"Tag lida: {decode_epc(epc)}")
        else:
            epc = choice

        print(f"\nKeybinds disponiveis:")
        print(f"  Teclas normais: a-z, 0-9, simbolos")
        print(f"  Teclas especiais: {', '.join(SPECIAL_KEYS)}")
        key = input(f"\nQual tecla vincular a {decode_epc(epc)[:20]}? ").strip().lower()

        if not key:
            print("Cancelado.")
            input("Pressione ENTER para voltar...")
            return

        self.keybinds[epc] = key
        self.config["keybinds"] = self.keybinds
        self.config["reader_ip"] = self.config.get("reader_ip", "192.168.89.25")
        self.config["scanned_tags"] = self.tag_store.get_tags_for_config()
        save_config(self.config)

        print(f"\nKeybind cadastrado: {decode_epc(epc)[:20]} -> [{key}]")
        input("\nPressione ENTER para voltar...")

    def list_keybinds(self):
        self.clear_screen()
        self.print_header("KEYBINDS CADASTRADOS")

        if not self.keybinds:
            print("\nNenhum keybind cadastrado.")
            print("Use a opcao 3 para cadastrar keybinds.")
        else:
            print(f"\n{'EPC':<26} {'KEYBIND':<12}")
            print("-" * 40)
            for epc, key in sorted(self.keybinds.items()):
                epc_display = decode_epc(epc)[:24]
                print(f"{epc_display:<26} {key:<12}")

            print(f"\nTotal: {len(self.keybinds)} keybind(s)")

        input("\nPressione ENTER para voltar...")

    def remove_keybind(self):
        if not self.keybinds:
            print("\nNenhum keybind cadastrado.")
            input("Pressione ENTER para voltar...")
            return

        self.clear_screen()
        self.print_header("REMOVER KEYBIND")
        print()

        for i, (epc, key) in enumerate(self.keybinds.items(), 1):
            epc_display = decode_epc(epc)[:24]
            print(f"  {i}. {epc_display} -> [{key}]")

        print()
        choice = input("Numero do keybind para remover (0=cancelar): ").strip()

        if choice == "0" or not choice:
            return

        try:
            idx = int(choice) - 1
            epc = list(self.keybinds.keys())[idx]
            key = self.keybinds.pop(epc)
            self.config["keybinds"] = self.keybinds
            save_config(self.config)
            print(f"\nKeybind removido: {decode_epc(epc)[:20]} -> [{key}]")
        except (ValueError, IndexError):
            print("\nSelecao invalida.")

        input("\nPressione ENTER para voltar...")

    def configure_ip(self):
        self.clear_screen()
        self.print_header("CONFIGURAR IP DO LEITOR")
        current_ip = self.config.get("reader_ip", "192.168.89.25")
        print(f"\nIP atual: {current_ip}")
        new_ip = input("\nNovo IP (Enter para manter): ").strip()

        if new_ip:
            self.config["reader_ip"] = new_ip
            save_config(self.config)
            print(f"\nIP atualizado para: {new_ip}")
        else:
            print("\nIP mantido.")

        input("\nPressione ENTER para voltar...")

    def start_game(self):
        if not self.keybinds:
            print(
                "\nNenhum keybind cadastrado. Cadastre keybinds antes de iniciar o jogo."
            )
            input("Pressione ENTER para voltar...")
            return

        if not self.scanner or not self.scanner.connected:
            if not self.connect_reader():
                input("\nPressione ENTER para voltar...")
                return

        self._game_mode = True
        self.clear_screen()
        self.print_header("MODO JOGO ATIVO")
        print("\nJogo iniciado! Passe as tags RFID para enviar teclas.")
        print("Pressione Ctrl+C para parar.\n")
        print("Keybinds ativos:")
        for epc, key in self.keybinds.items():
            print(f"  {decode_epc(epc)[:24]} -> [{key}]")
        print()

        try:
            while True:
                if self.scanner:
                    self.scanner.wait(timeout=1.0)
                    if not self.scanner.is_alive():
                        print("\nConexao com leitor perdida!")
                        break
                else:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self._game_mode = False

    def run(self):
        self.clear_screen()
        print("Inicializando...")
        time.sleep(0.5)

        try:
            while True:
                self.print_menu()
                choice = input("Opcao: ").strip()

                if choice == "1":
                    self.scan_tags()
                elif choice == "2":
                    self.list_scanned_tags()
                elif choice == "3":
                    self.register_keybind()
                elif choice == "4":
                    self.list_keybinds()
                elif choice == "5":
                    self.remove_keybind()
                elif choice == "6":
                    self.configure_ip()
                elif choice == "7":
                    self.start_game()
                elif choice == "0":
                    print("\nEncerrando...")
                    break
                else:
                    print("\nOpcao invalida.")
                    time.sleep(1)
        finally:
            self.disconnect_reader()


def main():
    cli = RFIDGameCLI()
    cli.run()


if __name__ == "__main__":
    main()
