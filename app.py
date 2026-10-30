from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import winreg
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from tkinter import messagebox, ttk

import vortex
from runner import DownloadRunner, RunnerConfig


APP_NAME = "Nexus Clicker"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NexusClickerDesktop"
CONFIG_PATH = APP_DIR / "settings.json"
LOG_PATH = APP_DIR / "desktop.log"
TEXT = {
    "en": {
        "language_title": "Choose your language / Выберите язык",
        "language_prompt": "This sets the language of the app.",
        "english": "English",
        "russian": "Русский",
        "continue": "Continue",
        "welcome_title": "Welcome to Nexus Clicker",
        "welcome_body": (
            "While Vortex downloads a collection, Nexus Clicker clicks "
            "\"Download manually\" in Vortex and \"Slow download\" on Nexus Mods for you.\n\n"
            "Setup takes three steps: choose your browser, add the extension, connect Vortex."
        ),
        "vortex_not_running": "Vortex isn't open. Click Start Vortex and the app will open it for you.",
        "vortex_start": "Start Vortex",
        "vortex_err_not_found": "Couldn't find Vortex on this PC. Open Vortex yourself once, then click Restart Vortex.",
        "vortex_err_close_timeout": "Vortex didn't close within a minute. Close it yourself (check the taskbar tray too), then click Start Vortex.",
        "vortex_err_start_timeout": "Vortex was started but hasn't finished opening. Wait until its window is up, then click Check again.",
        "default_browser_suffix": " (default)",
        "vortex_accessible": "Vortex is ready.",
        "vortex_connected": "Connected",
        "vortex_inaccessible": "Vortex is open, but the app can't see its buttons yet. Click Restart Vortex to fix this.",
        "vortex_checking": "Checking Vortex…",
        "vortex_check_error": "Couldn't check Vortex:",
        "vortex_apply_patch": "Restart Vortex",
        "vortex_patch_confirm": "Vortex will close normally and reopen in a mode that lets Nexus Clicker see its buttons. Nothing is force-closed. Finish what you're doing in Vortex first. Continue?",
        "vortex_patch_running": "Opening Vortex. This can take up to a minute…",
        "vortex_patch_success": "Vortex is ready.",
        "vortex_patch_error": "Couldn't restart Vortex:",
        "browser_title": "Choose your browser",
        "browser_prompt": "Pick your default browser. That's where Vortex opens mod pages.",
        "no_browser": "No supported browser found. Install Firefox, Chrome, Edge or Yandex Browser, then click Scan again.",
        "scan_browsers": "Scan again",
        "extension_title": "Add the extension",
        "extension_intro": "The Nexus Clicker extension clicks \"Slow download\" on mod pages. Add it to your browser:",
        "extension_path_label": "Extension location:",
        "chrome_step1": "1. Your browser opens its extensions page. If it doesn't, click Open extensions page below.",
        "chrome_step2": "2. Turn on Developer mode.",
        "chrome_step3": "3. Click Load unpacked and select the folder shown below.",
        "chrome_step4": "4. Make sure Nexus Clicker is switched on. Keep this folder next to NexusClicker.exe.",
        "firefox_step1": "1. Firefox opens its add-on debugging page. If it doesn't, click Open extensions page below.",
        "firefox_step2": "2. Click Load Temporary Add-on…",
        "firefox_step3": "3. Select the manifest.json file shown below. If Firefox then opens a Nexus Clicker tab, click Allow there.",
        "firefox_step4": "4. Firefox removes this add-on when it restarts, so repeat these steps after every Firefox restart.",
        "copy_location": "Copy location",
        "open_extensions": "Open extensions page",
        "open_folder": "Open folder",
        "extension_confirm": "I added the extension and it's switched on",
        "extension_update": "The extension was updated. Remove the old Nexus Clicker from your browser first, then add it again as shown below.",
        "extension_policy": "Browsers don't let apps add extensions by themselves, so this one step is manual.",
        "vortex_title": "Connect Vortex",
        "vortex_intro": "Nexus Clicker needs Vortex running in a mode where it can see Vortex's buttons. The check below tells you what to do.",
        "vortex_check_accessibility": "Check again",
        "start_automation": "Start",
        "back": "Back",
        "main_title": "Nexus Clicker",
        "view_menu": "View",
        "dark_mode": "Dark mode",
        "status": "Status",
        "browser": "Browser",
        "vortex": "Vortex",
        "extension": "Extension",
        "successful_actions": "Download clicks",
        "successful_actions_note": "Counts clicks on \"Download manually\" in Vortex. It doesn't check that downloads finished.",
        "scan_health_starting": "Watching Vortex: starting…",
        "scan_health": "Vortex checks: {scans} | errors: {errors}",
        "scan_health_stale": "Vortex hasn't responded for a while. Check that it's still open. The app keeps trying.",
        "pause": "Pause",
        "resume": "Resume",
        "restart": "Restart",
        "exit": "Exit",
        "recheck": "Check setup",
        "activity": "Now",
        "log": "Log",
        "checking": "Checking your setup…",
        "ready": "Setup",
        "running": "Running",
        "resuming": "Resuming…",
        "paused": "Paused",
        "stopped": "Stopped",
        "restart_wait": "Restarting…",
        "restart_timeout": "The previous run hasn't stopped yet. If this doesn't clear up, close and reopen Nexus Clicker.",
        "recheck_ok": "Everything looks ready.",
        "recheck_browser_missing": "Your browser can't be found anymore. Please go through setup again.",
        "recheck_extension_missing": "The extension files are missing. Please go through setup again.",
        "extension_location_error": "Couldn't create the extension folder next to NexusClicker.exe. Move the app to a folder you can save files in (for example C:\\NexusClicker) and try again:",
        "setup_required": "Tick the box to confirm you added the extension.",
        "current_waiting": "Waiting for the next mod in Vortex",
        "runner_error": "Error:",
        "close_confirm": "Stop Nexus Clicker and exit?",
        "save_error": "Couldn't save settings:",
        "required_setup": "Setup isn't finished. Please go through the setup steps.",
    },
    "ru": {
        "language_title": "Выберите язык / Choose your language",
        "language_prompt": "Язык интерфейса программы.",
        "english": "English",
        "russian": "Русский",
        "continue": "Продолжить",
        "welcome_title": "Добро пожаловать в Nexus Clicker",
        "welcome_body": (
            "Пока Vortex скачивает коллекцию, Nexus Clicker сам нажимает "
            "«Download manually» в Vortex и «Slow download» на сайте Nexus Mods.\n\n"
            "Настройка займёт три шага: выбрать браузер, добавить расширение и подключить Vortex."
        ),
        "vortex_not_running": "Vortex не открыт. Нажмите «Запустить Vortex», и программа откроет его сама.",
        "vortex_start": "Запустить Vortex",
        "vortex_err_not_found": "Не удалось найти Vortex на этом компьютере. Откройте Vortex сами один раз, затем нажмите «Перезапустить Vortex».",
        "vortex_err_close_timeout": "Vortex не закрылся за минуту. Закройте его сами (проверьте и значок в трее), затем нажмите «Запустить Vortex».",
        "vortex_err_start_timeout": "Vortex запущен, но ещё не открылся. Дождитесь его окна и нажмите «Проверить снова».",
        "default_browser_suffix": " (по умолчанию)",
        "vortex_accessible": "Vortex готов к работе.",
        "vortex_connected": "Подключён",
        "vortex_inaccessible": "Vortex открыт, но программа пока не видит его кнопки. Нажмите «Перезапустить Vortex», чтобы это исправить.",
        "vortex_checking": "Проверяем Vortex…",
        "vortex_check_error": "Не удалось проверить Vortex:",
        "vortex_apply_patch": "Перезапустить Vortex",
        "vortex_patch_confirm": "Vortex закроется обычным образом и откроется снова в режиме, в котором Nexus Clicker видит его кнопки. Принудительно ничего не закрывается. Сначала завершите свои действия в Vortex. Продолжить?",
        "vortex_patch_running": "Открываем Vortex. Это может занять до минуты…",
        "vortex_patch_success": "Vortex готов к работе.",
        "vortex_patch_error": "Не удалось перезапустить Vortex:",
        "browser_title": "Выберите браузер",
        "browser_prompt": "Выберите браузер по умолчанию: именно в нём Vortex открывает страницы модов.",
        "no_browser": "Подходящий браузер не найден. Установите Firefox, Chrome, Edge или Яндекс Браузер и нажмите «Найти снова».",
        "scan_browsers": "Найти снова",
        "extension_title": "Добавьте расширение",
        "extension_intro": "Расширение Nexus Clicker нажимает «Slow download» на страницах модов. Добавьте его в браузер:",
        "extension_path_label": "Где лежит расширение:",
        "chrome_step1": "1. Браузер сам откроет страницу расширений. Если этого не произошло, нажмите «Открыть страницу расширений» ниже.",
        "chrome_step2": "2. Включите «Режим разработчика».",
        "chrome_step3": "3. Нажмите «Загрузить распакованное расширение» и выберите папку, указанную ниже.",
        "chrome_step4": "4. Проверьте, что Nexus Clicker включён. Папка должна оставаться рядом с NexusClicker.exe.",
        "firefox_step1": "1. Firefox сам откроет страницу отладки дополнений. Если этого не произошло, нажмите «Открыть страницу расширений» ниже.",
        "firefox_step2": "2. Нажмите «Загрузить временное дополнение…»",
        "firefox_step3": "3. Выберите файл manifest.json, указанный ниже. Если Firefox откроет вкладку Nexus Clicker, нажмите в ней «Allow / Разрешить».",
        "firefox_step4": "4. Firefox удаляет такое дополнение при перезапуске, поэтому после каждого перезапуска Firefox повторяйте эти шаги.",
        "copy_location": "Скопировать путь",
        "open_extensions": "Открыть страницу расширений",
        "open_folder": "Открыть папку",
        "extension_confirm": "Я добавил(а) расширение, и оно включено",
        "extension_update": "Расширение обновилось. Сначала удалите старый Nexus Clicker из браузера, затем добавьте его заново, как показано ниже.",
        "extension_policy": "Браузеры не разрешают программам добавлять расширения самостоятельно, поэтому этот шаг нужно сделать вручную.",
        "vortex_title": "Подключите Vortex",
        "vortex_intro": "Nexus Clicker нужен Vortex, запущенный в режиме, в котором видны его кнопки. Проверка ниже подскажет, что делать.",
        "vortex_check_accessibility": "Проверить снова",
        "start_automation": "Запустить",
        "back": "Назад",
        "main_title": "Nexus Clicker",
        "view_menu": "Вид",
        "dark_mode": "Тёмная тема",
        "status": "Состояние",
        "browser": "Браузер",
        "vortex": "Vortex",
        "extension": "Расширение",
        "successful_actions": "Нажатий на загрузку",
        "successful_actions_note": "Считает нажатия «Download manually» в Vortex. Не проверяет, завершилась ли загрузка.",
        "scan_health_starting": "Следим за Vortex: запуск…",
        "scan_health": "Проверок Vortex: {scans} | ошибок: {errors}",
        "scan_health_stale": "Vortex давно не отвечает. Проверьте, что он открыт. Программа продолжает попытки.",
        "pause": "Пауза",
        "resume": "Продолжить",
        "restart": "Перезапустить",
        "exit": "Выход",
        "recheck": "Проверить настройку",
        "activity": "Сейчас",
        "log": "Журнал",
        "checking": "Проверяем настройки…",
        "ready": "Настройка",
        "running": "Работает",
        "resuming": "Продолжаем…",
        "paused": "На паузе",
        "stopped": "Остановлено",
        "restart_wait": "Перезапуск…",
        "restart_timeout": "Предыдущий запуск ещё не остановился. Если это не пройдёт, закройте и снова откройте Nexus Clicker.",
        "recheck_ok": "Всё готово.",
        "recheck_browser_missing": "Выбранный браузер больше не найден. Пройдите настройку заново.",
        "recheck_extension_missing": "Файлы расширения пропали. Пройдите настройку заново.",
        "extension_location_error": "Не удалось создать папку расширения рядом с NexusClicker.exe. Переместите программу в папку, где можно сохранять файлы (например, C:\\NexusClicker), и попробуйте снова:",
        "setup_required": "Поставьте галочку, что расширение добавлено.",
        "current_waiting": "Ждём следующий мод в Vortex",
        "runner_error": "Ошибка:",
        "close_confirm": "Остановить Nexus Clicker и выйти?",
        "save_error": "Не удалось сохранить настройки:",
        "required_setup": "Настройка не завершена. Пройдите шаги настройки.",
    },
}


@dataclass(frozen=True)
class BrowserOption:
    key: str
    name: str
    executable: Path
    extensions_url: str
    is_default: bool = False


# key, display name, executable, usual install paths, extensions page
BROWSERS = (
    (
        "firefox",
        "Mozilla Firefox",
        "firefox.exe",
        ("Mozilla Firefox/firefox.exe", "Firefox Developer Edition/firefox.exe", "Firefox Nightly/firefox.exe"),
        "about:debugging#/runtime/this-firefox",
    ),
    ("chrome", "Google Chrome", "chrome.exe", ("Google/Chrome/Application/chrome.exe",), "chrome://extensions"),
    ("edge", "Microsoft Edge", "msedge.exe", ("Microsoft/Edge/Application/msedge.exe",), "edge://extensions"),
    ("yandex", "Yandex Browser", "browser.exe", ("Yandex/YandexBrowser/Application/browser.exe",), "browser://extensions"),
)
BROWSER_KEYS = {definition[0] for definition in BROWSERS}
EXTENSION_FOLDER = "extension"


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return root / relative


def _read_registry(hive, subkey: str, name: str | None = None) -> str | None:
    try:
        with winreg.OpenKey(hive, subkey) as key:
            value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return str(value)


def _executable_from_command(value: str | None) -> Path | None:
    if not value:
        return None
    value = os.path.expandvars(str(value)).strip()
    match = re.match(r'^"([^"]+?\.exe)"', value, re.IGNORECASE) or re.match(
        r"^(.+?\.exe)(?=$|[\s,])", value, re.IGNORECASE
    )
    return Path(match.group(1)) if match else None


def _registry_executable(hive, subkey: str) -> Path | None:
    path = _executable_from_command(_read_registry(hive, subkey))
    return path if path and path.is_file() else None


def browser_key_for(path: Path) -> str | None:
    name = PureWindowsPath(str(path)).name.casefold()
    if name == "firefox.exe":
        return "firefox"
    if name == "chrome.exe":
        return "chrome"
    if name == "msedge.exe":
        return "edge"
    if name == "browser.exe" and "yandex" in str(path).casefold():
        return "yandex"
    return None


def default_browser_executable() -> Path | None:
    """The browser Windows opens links with, which is also where Vortex opens mod pages."""
    for scheme in ("https", "http"):
        for choice in ("UserChoiceLatest", "UserChoice"):
            prog_id = _read_registry(
                winreg.HKEY_CURRENT_USER,
                rf"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\{scheme}\{choice}",
                "ProgId",
            )
            if not prog_id:
                continue
            for hive, subkey in (
                (winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open\command"),
                (winreg.HKEY_LOCAL_MACHINE, rf"Software\Classes\{prog_id}\shell\open\command"),
                (winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\shell\open\command"),
            ):
                path = _executable_from_command(_read_registry(hive, subkey))
                if path:
                    return path
    return None


def _registered_browsers() -> list[Path]:
    """Browsers that registered themselves with Windows (Settings > Default apps)."""
    paths: list[Path] = []
    for hive, subkey in (
        (winreg.HKEY_CURRENT_USER, r"Software\Clients\StartMenuInternet"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Clients\StartMenuInternet"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Clients\StartMenuInternet"),
    ):
        try:
            root = winreg.OpenKey(hive, subkey)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    child = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                path = _executable_from_command(
                    _read_registry(hive, rf"{subkey}\{child}\shell\open\command")
                )
                if path:
                    paths.append(path)
    return paths


def detect_browsers() -> list[BrowserOption]:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    program_files = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
    ]
    default = default_browser_executable()
    registered = _registered_browsers()
    results: list[BrowserOption] = []
    for key, name, executable_name, relatives, url in BROWSERS:
        candidates: list[Path] = []
        if default and browser_key_for(default) == key:
            candidates.append(default)
        candidates += [path for path in registered if browser_key_for(path) == key]
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            registry_path = _registry_executable(
                hive,
                rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}",
            )
            if registry_path and browser_key_for(registry_path) == key:
                candidates.append(registry_path)
        for relative in relatives:
            candidates.append(local / relative)
            candidates += [root / relative for root in program_files]
        executable = next((path for path in candidates if path.is_file()), None)
        if executable:
            is_default = bool(default) and browser_key_for(default) == key
            results.append(BrowserOption(key, name, executable, url, is_default))
    return results


def extension_fingerprint(directory: Path | None = None, browser_key: str = "chrome") -> str:
    source = directory or resource_path(extension_folder_name(browser_key))
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Bundled browser extension is missing: {source}")
    fingerprint = hashlib.sha256()
    for path in sorted(source.iterdir()):
        if path.is_file() and path.name != ".bundled-version":
            fingerprint.update(path.name.encode("utf-8"))
            fingerprint.update(path.read_bytes())
    return fingerprint.hexdigest()


def extension_folder_name(browser_key: str) -> str:
    """One extension folder works in every supported browser."""
    if browser_key not in BROWSER_KEYS:
        raise ValueError(f"Unsupported browser: {browser_key}")
    return EXTENSION_FOLDER


def extension_directory(browser_key: str) -> Path:
    executable_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    return executable_dir / extension_folder_name(browser_key)


def install_extension_files(browser_key: str) -> tuple[Path, bool]:
    folder_name = extension_folder_name(browser_key)
    source = resource_path(folder_name)
    destination = extension_directory(browser_key)
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Bundled {browser_key} extension is missing: {source}")
    if source.resolve() == destination.resolve():
        return destination, False
    marker = destination / ".bundled-version"
    digest = extension_fingerprint(source)
    installed_matches = False
    if destination.is_dir():
        try:
            installed_matches = extension_fingerprint(destination) == digest
        except FileNotFoundError:
            installed_matches = False
    changed = (
        not marker.is_file()
        or marker.read_text(encoding="utf-8").strip() != digest
        or not installed_matches
    )
    if changed:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        marker.write_text(digest, encoding="utf-8")
    return destination, changed


class DesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("760x620")
        self.root.minsize(680, 540)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.runner: DownloadRunner | None = None
        self.worker: threading.Thread | None = None
        self.settings = self._load_settings()
        self.language = tk.StringVar(value=self.settings.get("language", "en"))
        self.browser_choice = tk.StringVar(value=self.settings.get("browser", ""))
        self.dark_mode = tk.BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        self.extension_confirmed = tk.BooleanVar(value=False)
        self.extension_confirmed_browser: str | None = None
        self.extension_continue_button: ttk.Button | None = None
        self.status = tk.StringVar()
        self.browsers: list[BrowserOption] = []
        self.vortex_ready = False
        self.vortex_check_pending = False
        self.vortex_patch_pending = False
        self.restart_after_vortex_check = False
        self.restart_deadline = 0.0
        self.last_scan_health_time = 0.0
        self.scan_health_warning = False
        self.paused = False
        self.page = "language"
        self._build_shell()
        self._build_menu()
        self._apply_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._drain_events)
        self.show_language_page()

    def t(self, key: str) -> str:
        return TEXT[self.language.get()].get(key, key)

    def _load_settings(self) -> dict:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError):
            logging.exception("Could not read settings file %s", CONFIG_PATH)
            return {}

    def _save_settings(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        browser = self.selected_browser()
        if not browser:
            raise RuntimeError(self.t("required_setup"))
        settings = {
            "language": self.language.get(),
            "browser": browser.key,
            "dark_mode": self.dark_mode.get(),
            "extension_confirmed": True,
            "extension_fingerprint": extension_fingerprint(
                extension_directory(browser.key)
            ),
        }
        temporary = CONFIG_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        temporary.replace(CONFIG_PATH)
        self.settings = settings

    def _build_shell(self) -> None:
        self.container = ttk.Frame(self.root, padding=22)
        self.container.pack(fill="both", expand=True)
        self.content = ttk.Frame(self.container)
        self.content.pack(fill="both", expand=True)

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.root)
        view_menu = tk.Menu(self.menu, tearoff=False)
        view_menu.add_checkbutton(
            label=self.t("dark_mode"),
            variable=self.dark_mode,
            command=self._toggle_dark_mode,
        )
        self.menu.add_cascade(label=self.t("view_menu"), menu=view_menu)
        self.root.configure(menu=self.menu)
        self.view_menu = view_menu

    def _apply_theme(self) -> None:
        dark = self.dark_mode.get()
        colors = (
            {
                "background": "#202124",
                "surface": "#292a2d",
                "foreground": "#e8eaed",
                "muted": "#bdc1c6",
                "field": "#303134",
                "select": "#3c4043",
                "accent": "#8ab4f8",
            }
            if dark
            else {
                "background": "#f0f0f0",
                "surface": "#f7f7f7",
                "foreground": "#202124",
                "muted": "#5f6368",
                "field": "#ffffff",
                "select": "#d9e2f3",
                "accent": "#1a73e8",
            }
        )
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=colors["background"], foreground=colors["foreground"])
        style.configure("TFrame", background=colors["background"])
        style.configure("TLabel", background=colors["background"], foreground=colors["foreground"])
        style.configure(
            "TLabelframe",
            background=colors["background"],
            foreground=colors["foreground"],
            bordercolor=colors["muted"],
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["background"],
            foreground=colors["foreground"],
        )
        style.configure(
            "TButton",
            background=colors["surface"],
            foreground=colors["foreground"],
            bordercolor=colors["muted"],
            focuscolor=colors["accent"],
        )
        style.map(
            "TButton",
            background=[("active", colors["select"]), ("disabled", colors["background"])],
            foreground=[("disabled", colors["muted"])],
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["field"],
            foreground=colors["foreground"],
            insertcolor=colors["foreground"],
        )
        style.configure(
            "TCheckbutton",
            background=colors["background"],
            foreground=colors["foreground"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", colors["background"])],
            foreground=[("disabled", colors["muted"])],
        )
        style.configure(
            "TRadiobutton",
            background=colors["background"],
            foreground=colors["foreground"],
        )
        style.map(
            "TRadiobutton",
            background=[("active", colors["background"])],
            foreground=[("disabled", colors["muted"])],
        )
        self.root.configure(background=colors["background"])
        self.menu.configure(
            background=colors["surface"],
            foreground=colors["foreground"],
            activebackground=colors["select"],
            activeforeground=colors["foreground"],
        )
        self.view_menu.configure(
            background=colors["surface"],
            foreground=colors["foreground"],
            activebackground=colors["select"],
            activeforeground=colors["foreground"],
            selectcolor=colors["field"],
        )
        if hasattr(self, "log_box"):
            self.log_box.configure(
                background=colors["field"],
                foreground=colors["foreground"],
                insertbackground=colors["foreground"],
                selectbackground=colors["select"],
                selectforeground=colors["foreground"],
            )

    def _toggle_dark_mode(self) -> None:
        previous = not self.dark_mode.get()
        self._apply_theme()
        updated_settings = {**self.settings, "dark_mode": self.dark_mode.get()}
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(updated_settings, indent=2), encoding="utf-8")
            temporary.replace(CONFIG_PATH)
        except OSError as exc:
            self.dark_mode.set(previous)
            self._apply_theme()
            messagebox.showerror(APP_NAME, f"{self.t('save_error')} {exc}")
            return
        self.settings = updated_settings

    def _clear(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _heading(self, title: str, body: str | None = None) -> None:
        ttk.Label(self.content, text=title, font=("Segoe UI", 19, "bold")).pack(anchor="w", pady=(0, 10))
        if body:
            ttk.Label(self.content, text=body, wraplength=690, justify="left").pack(anchor="w", pady=(0, 14))

    def _footer(self, back: bool, next_command, next_text: str | None = None) -> ttk.Button:
        footer = ttk.Frame(self.content)
        footer.pack(fill="x", side="bottom", pady=(18, 0))
        if back:
            ttk.Button(footer, text=self.t("back"), command=self._go_back).pack(side="left")
        button = ttk.Button(
            footer,
            text=next_text or self.t("continue"),
            command=next_command,
        )
        button.pack(side="right")
        return button

    def show_language_page(self) -> None:
        self.page = "language"
        self._clear()
        self._heading(TEXT[self.language.get()]["language_title"], TEXT[self.language.get()]["language_prompt"])
        choices = ttk.Frame(self.content)
        choices.pack(anchor="w", pady=8)
        ttk.Radiobutton(
            choices,
            text=TEXT["en"]["english"],
            variable=self.language,
            value="en",
        ).pack(anchor="w", pady=5)
        ttk.Radiobutton(
            choices,
            text=TEXT["ru"]["russian"],
            variable=self.language,
            value="ru",
        ).pack(anchor="w", pady=5)
        self._footer(False, self._continue_language, TEXT[self.language.get()]["continue"])

    def _continue_language(self) -> None:
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            settings = self._load_settings()
            settings["language"] = self.language.get()
            temporary = CONFIG_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            temporary.replace(CONFIG_PATH)
            self.settings = settings
            self._build_menu()
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{self.t('save_error')} {exc}")
            return
        self.show_welcome()

    def show_welcome(self) -> None:
        self.page = "welcome"
        self._clear()
        self._heading(self.t("welcome_title"), self.t("welcome_body"))
        self._footer(True, self._continue_after_welcome)

    def _continue_after_welcome(self) -> None:
        # The browser step is shown every time, so a different browser can be
        # picked on any launch. The last choice (or Windows' default) is preselected.
        self.extension_update_required = False
        self.show_browser_page()

    def show_browser_page(self) -> None:
        self.page = "browser"
        self.browsers = detect_browsers()
        self.extensions_opened_for = None
        self._clear()
        self._heading(self.t("browser_title"), self.t("browser_prompt"))
        if not self.browsers:
            ttk.Label(self.content, text=self.t("no_browser"), wraplength=690).pack(anchor="w", pady=12)
            ttk.Button(self.content, text=self.t("scan_browsers"), command=self.show_browser_page).pack(anchor="w")
            self._footer(True, self.show_browser_page)
            return

        found = {browser.key: browser for browser in self.browsers}
        if self.browser_choice.get() not in found:
            preferred = next((b for b in self.browsers if b.is_default), self.browsers[0])
            self.browser_choice.set(preferred.key)
        for browser in self.browsers:
            label = f"{browser.name} ({browser.executable})"
            if browser.is_default:
                label += self.t("default_browser_suffix")
            ttk.Radiobutton(
                self.content,
                text=label,
                variable=self.browser_choice,
                value=browser.key,
            ).pack(anchor="w", pady=7)
        ttk.Button(self.content, text=self.t("scan_browsers"), command=self.show_browser_page).pack(anchor="w", pady=10)
        self._footer(True, self.show_extension_page)

    def selected_browser(self) -> BrowserOption | None:
        return next((b for b in self.browsers if b.key == self.browser_choice.get()), None)

    def show_extension_page(self) -> None:
        browser = self.selected_browser()
        if not browser:
            self.show_browser_page()
            return
        if self.extension_confirmed_browser != browser.key:
            self.extension_confirmed.set(False)
        try:
            extension_folder, changed = install_extension_files(browser.key)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror(
                APP_NAME,
                f"{self.t('extension_location_error')}\n{exc}",
            )
            return
        self.extension_update_required = (
            getattr(self, "extension_update_required", False)
            or (changed and bool(self.settings.get("extension_confirmed")))
        )
        if self.extension_update_required:
            self.extension_confirmed.set(False)
            self.extension_confirmed_browser = None
        self.page = "extension"
        self._clear()
        intro = self.t("extension_intro")
        if self.extension_update_required:
            intro = f"{self.t('extension_update')}\n\n{intro}"
        self._heading(self.t("extension_title"), intro)
        browser_prefix = "firefox" if browser.key == "firefox" else "chrome"
        for key in (f"{browser_prefix}_step1", f"{browser_prefix}_step2", f"{browser_prefix}_step3"):
            ttk.Label(self.content, text=self.t(key), wraplength=690).pack(anchor="w", pady=3)
        shown_location = (
            extension_folder / "manifest.json"
            if browser.key == "firefox"
            else extension_folder
        )
        ttk.Label(self.content, text=self.t("extension_path_label")).pack(anchor="w", pady=(8, 2))
        self.extension_path = tk.StringVar(value=str(shown_location))
        ttk.Entry(
            self.content,
            textvariable=self.extension_path,
            state="readonly",
        ).pack(fill="x", pady=(2, 8))
        ttk.Label(
            self.content,
            text=self.t(f"{browser_prefix}_step4"),
            wraplength=690,
        ).pack(anchor="w", pady=3)
        ttk.Label(
            self.content,
            text=self.t("extension_policy"),
            wraplength=690,
            foreground="#704214",
        ).pack(anchor="w", pady=(12, 8))
        actions = ttk.Frame(self.content)
        actions.pack(anchor="w", pady=5)
        ttk.Button(actions, text=self.t("open_extensions"), command=lambda: self._open_extensions(browser)).pack(side="left")
        ttk.Button(actions, text=self.t("open_folder"), command=lambda: os.startfile(str(extension_folder))).pack(side="left", padx=8)
        ttk.Button(actions, text=self.t("copy_location"), command=lambda: self._copy_extension_location(shown_location)).pack(side="left")
        ttk.Checkbutton(
            self.content,
            text=self.t("extension_confirm"),
            variable=self.extension_confirmed,
            command=self._extension_confirmation_changed,
        ).pack(anchor="w", pady=10)
        self.extension_continue_button = self._footer(
            True,
            self._continue_after_extension,
        )
        self._update_extension_continue_state()
        if getattr(self, "extensions_opened_for", None) != browser.key:
            self.extensions_opened_for = browser.key
            self.root.after(300, lambda: self._open_extensions(browser))

    def _extension_confirmation_changed(self) -> None:
        browser = self.selected_browser()
        if self.extension_confirmed.get() and browser:
            self.extension_confirmed_browser = browser.key
        else:
            self.extension_confirmed_browser = None
        self._update_extension_continue_state()

    def _update_extension_continue_state(self) -> None:
        if self.extension_continue_button:
            self.extension_continue_button.configure(
                state="normal" if self.extension_confirmed.get() else "disabled"
            )

    def _open_extensions(self, browser: BrowserOption) -> None:
        try:
            subprocess.Popen([str(browser.executable), browser.extensions_url], close_fds=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"{exc}")

    def _copy_extension_location(self, location: Path) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(str(location))
        self.root.update()

    def _continue_after_extension(self) -> None:
        if not self.extension_confirmed.get():
            return
        self.extension_update_required = False
        self.show_vortex_page()

    def show_vortex_page(self) -> None:
        self.page = "vortex"
        self._clear()
        self._heading(self.t("vortex_title"), self.t("vortex_intro"))
        self.vortex_state = tk.StringVar()
        ttk.Label(self.content, textvariable=self.vortex_state, wraplength=690).pack(anchor="w")
        self.vortex_check_button = ttk.Button(
            self.content,
            text=self.t("vortex_check_accessibility"),
            command=self._check_vortex_accessibility,
        )
        self.vortex_check_button.pack(anchor="w", pady=12)
        self.vortex_patch_button = ttk.Button(
            self.content,
            text=self.t("vortex_apply_patch"),
            command=self._apply_vortex_patch,
            state="disabled",
        )
        self.vortex_patch_button.pack(anchor="w", pady=(0, 12))
        self.start_button = self._footer(True, self._start_from_setup, self.t("start_automation"))
        self.start_button.configure(state="disabled")
        self._check_vortex_accessibility()

    def _check_vortex_accessibility(self) -> None:
        if self.vortex_check_pending:
            return
        self.vortex_check_pending = True
        self.vortex_ready = False
        if self.page == "vortex":
            self.vortex_state.set(self.t("vortex_checking"))
            self.vortex_check_button.configure(state="disabled")
        elif self.page == "main":
            self.status.set(self.t("vortex_checking"))
        threading.Thread(
            target=self._probe_vortex_accessibility,
            name="vortex-accessibility-check",
            daemon=True,
        ).start()

    def _probe_vortex_accessibility(self) -> None:
        try:
            state = vortex.accessibility_state()
            if state == "unknown":
                state = "ready" if vortex.ui_has_buttons() else "needs_restart"
            result = state if state in {"ready", "not_running"} else "inaccessible"
            self.events.put(("vortex_check", result))
        except Exception as exc:
            logging.exception("Could not check Vortex.")
            self.events.put(("vortex_check_error", str(exc)))

    def _apply_vortex_patch(self) -> None:
        if self.vortex_patch_pending:
            return
        try:
            running = vortex.is_running()
        except Exception:
            logging.exception("Could not check whether Vortex is running.")
            running = True
        if running and not messagebox.askyesno(APP_NAME, self.t("vortex_patch_confirm")):
            return
        self.vortex_patch_pending = True
        self.vortex_ready = False
        self.vortex_state.set(self.t("vortex_patch_running"))
        self.vortex_check_button.configure(state="disabled")
        self.vortex_patch_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        threading.Thread(
            target=self._restart_vortex_worker,
            name="vortex-accessibility-restart",
            daemon=True,
        ).start()

    def _restart_vortex_worker(self) -> None:
        try:
            vortex.start_with_accessibility()
        except vortex.VortexError as exc:
            logging.warning("Could not start Vortex: %s", exc.code)
            self.events.put(("vortex_patch_error", exc.code))
        except Exception as exc:
            logging.exception("Could not start Vortex with accessibility.")
            self.events.put(("vortex_patch_error", str(exc)))
        else:
            self.events.put(("vortex_patch", "ready"))

    def _start_from_setup(self) -> None:
        if not self.extension_confirmed.get():
            messagebox.showwarning(APP_NAME, self.t("setup_required"))
            return
        if not self.vortex_ready:
            self._check_vortex_accessibility()
            return
        try:
            self._save_settings()
            self._start_runner()
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
            messagebox.showerror(APP_NAME, f"{self.t('save_error')} {exc}")

    def _start_runner(self) -> None:
        browser = self.selected_browser()
        if not browser or not extension_directory(browser.key).is_dir():
            raise RuntimeError(self.t("required_setup"))
        config = RunnerConfig(
            poll_interval=0.25,
            last_item_path=APP_DIR / "last-item.txt",
            success_count_path=APP_DIR / "successful-actions.txt",
            language=self.language.get(),
        )
        self.events = queue.Queue()
        self.runner = DownloadRunner(config, self.events)
        self.worker = threading.Thread(target=self.runner.run, name="download-runner", daemon=True)
        self.worker.start()
        self._show_main()

    def _show_main(self) -> None:
        self.page = "main"
        self._clear()
        browser = self.selected_browser()
        self._heading(self.t("main_title"))
        details = ttk.LabelFrame(self.content, text=self.t("ready"), padding=10)
        details.pack(fill="x")
        ttk.Label(details, text=f"{self.t('browser')}: {browser.name if browser else '—'}").pack(anchor="w", pady=2)
        ttk.Label(details, text=f"{self.t('vortex')}: {self.t('vortex_connected')}").pack(anchor="w", pady=2)
        browser = self.selected_browser()
        extension_path = extension_directory(browser.key) if browser else Path()
        ttk.Label(details, text=f"{self.t('extension')}: {extension_path}").pack(anchor="w", pady=2)
        self.download_count_var = tk.StringVar(value="0")
        ttk.Label(
            details,
            textvariable=self.download_count_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(8, 2))
        ttk.Label(
            details,
            text=self.t("successful_actions_note"),
            wraplength=660,
        ).pack(anchor="w", pady=(0, 3))
        ttk.Label(self.content, text=self.t("activity"), font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 3))
        ttk.Label(self.content, textvariable=self.status, wraplength=690).pack(anchor="w", pady=(0, 8))
        self.scan_health_var = tk.StringVar(value=self.t("scan_health_starting"))
        ttk.Label(self.content, textvariable=self.scan_health_var, wraplength=690).pack(anchor="w")
        buttons = ttk.Frame(self.content)
        buttons.pack(fill="x", pady=8)
        self.pause_button = ttk.Button(buttons, text=self.t("pause"), command=self._toggle_pause)
        self.pause_button.pack(side="left")
        ttk.Button(buttons, text=self.t("restart"), command=self._restart_runner).pack(side="left", padx=8)
        ttk.Button(buttons, text=self.t("recheck"), command=self._quick_recheck).pack(side="left")
        ttk.Button(buttons, text=self.t("exit"), command=self._on_close).pack(side="right")
        ttk.Label(self.content, text=self.t("log")).pack(anchor="w")
        self.log_box = tk.Text(self.content, height=13, wrap="word", state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))
        self._apply_theme()

    def _toggle_pause(self) -> None:
        if not self.runner or not self.worker or not self.worker.is_alive():
            return
        if self.runner.pause_event.is_set():
            self.runner.pause()
            self.paused = True
            self.status.set(self.t("paused"))
            self.pause_button.configure(text=self.t("resume"))
        else:
            self.runner.resume()
            self.paused = False
            self.last_scan_health_time = time.monotonic()
            self.scan_health_warning = False
            self.status.set(self.t("resuming"))
            self.pause_button.configure(text=self.t("pause"))

    def _restart_runner(self) -> None:
        if self.runner:
            self.runner.stop()
        self.status.set(self.t("restart_wait"))
        self.restart_deadline = time.monotonic() + 15
        self.root.after(250, self._finish_restart)

    def _finish_restart(self) -> None:
        if self.worker and self.worker.is_alive():
            if time.monotonic() >= self.restart_deadline:
                self.status.set(self.t("restart_timeout"))
                messagebox.showerror(APP_NAME, self.t("restart_timeout"))
                return
            self.root.after(250, self._finish_restart)
            return
        try:
            if not vortex.is_running():
                self.status.set(self.t("vortex_not_running"))
                return
        except Exception as exc:
            self.status.set(f"{self.t('vortex_check_error')} {exc}")
            return
        self.restart_after_vortex_check = True
        self._check_vortex_accessibility()

    def _quick_recheck(self) -> None:
        self.browsers = detect_browsers()
        browser = self.selected_browser()
        if not browser:
            self.status.set(self.t("recheck_browser_missing"))
            self.show_browser_page()
            return
        current_extension_dir = extension_directory(browser.key)
        if not current_extension_dir.joinpath("manifest.json").is_file():
            self.status.set(self.t("recheck_extension_missing"))
            self.show_extension_page()
            return
        try:
            _, extension_changed = install_extension_files(browser.key)
            if (
                self.settings.get("extension_fingerprint")
                != extension_fingerprint(current_extension_dir)
                or extension_changed
            ):
                self.extension_confirmed.set(False)
                self.extension_update_required = True
                self.show_extension_page()
                return
        except (OSError, ValueError):
            self.status.set(self.t("recheck_extension_missing"))
            self.show_extension_page()
            return
        self._check_vortex_accessibility()

    def _drain_events(self) -> None:
        while True:
            try:
                kind, text = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "vortex_check":
                self.vortex_check_pending = False
                self.vortex_ready = text == "ready"
                if self.page == "vortex":
                    status_key = {
                        "ready": "vortex_accessible",
                        "not_running": "vortex_not_running",
                        "inaccessible": "vortex_inaccessible",
                    }[text]
                    self.vortex_state.set(self.t(status_key))
                    self.vortex_check_button.configure(state="normal")
                    self.vortex_patch_button.configure(
                        state="disabled" if self.vortex_ready else "normal",
                        text=self.t("vortex_start" if text == "not_running" else "vortex_apply_patch"),
                    )
                    self.start_button.configure(
                        state="normal" if self.vortex_ready else "disabled"
                    )
                elif self.page == "main":
                    status_key = (
                        "recheck_ok" if self.vortex_ready else
                        "vortex_not_running" if text == "not_running" else
                        "vortex_inaccessible"
                    )
                    self.status.set(self.t(status_key))
                if self.restart_after_vortex_check:
                    self.restart_after_vortex_check = False
                    if self.vortex_ready:
                        self._start_runner()
            elif kind == "vortex_check_error":
                self.vortex_check_pending = False
                self.vortex_ready = False
                error = f"{self.t('vortex_check_error')} {text}"
                if self.page == "vortex":
                    self.vortex_state.set(error)
                    self.vortex_check_button.configure(state="normal")
                    self.vortex_patch_button.configure(state="normal")
                    self.start_button.configure(state="disabled")
                elif self.page == "main":
                    self.status.set(error)
                self.restart_after_vortex_check = False
            elif kind == "vortex_patch":
                self.vortex_patch_pending = False
                self.vortex_ready = True
                if self.page == "vortex":
                    self.vortex_state.set(self.t("vortex_patch_success"))
                    self.vortex_check_button.configure(state="normal")
                    self.vortex_patch_button.configure(state="disabled")
                    self.start_button.configure(state="normal")
                elif self.page == "main":
                    self.status.set(self.t("vortex_patch_success"))
            elif kind == "vortex_patch_error":
                self.vortex_patch_pending = False
                self.vortex_ready = False
                error_key = f"vortex_err_{text}"
                error = (
                    self.t(error_key)
                    if error_key in TEXT[self.language.get()]
                    else f"{self.t('vortex_patch_error')} {text}"
                )
                if self.page == "vortex":
                    self.vortex_state.set(error)
                    self.vortex_check_button.configure(state="normal")
                    self.vortex_patch_button.configure(state="normal")
                    self.start_button.configure(state="disabled")
                elif self.page == "main":
                    self.status.set(error)
            elif kind == "download_count":
                if self.page == "main":
                    self.download_count_var.set(
                        f"{self.t('successful_actions')}: {text}"
                    )
            elif kind == "health":
                try:
                    scans, errors = (int(value) for value in text.split("|", 1))
                except (TypeError, ValueError):
                    logging.error("Received invalid runner health data: %r", text)
                else:
                    self.last_scan_health_time = time.monotonic()
                    self.scan_health_warning = False
                    if self.page == "main":
                        self.scan_health_var.set(
                            self.t("scan_health").format(scans=scans, errors=errors)
                        )
            elif self.page == "main" and kind == "status":
                if self.runner and not self.runner.pause_event.is_set():
                    self.status.set(self.t("paused"))
                else:
                    self.status.set(text)
            elif self.page == "main" and kind == "log":
                self.log_box.configure(state="normal")
                self.log_box.insert("end", text + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        if (
            self.page == "main"
            and self.worker
            and self.worker.is_alive()
            and self.runner
            and self.runner.pause_event.is_set()
            and self.last_scan_health_time
            and time.monotonic() - self.last_scan_health_time > 10
            and not self.scan_health_warning
        ):
            self.scan_health_var.set(self.t("scan_health_stale"))
            self.scan_health_warning = True
        if self.page == "main" and self.worker and not self.worker.is_alive():
            self.pause_button.configure(state="disabled")
            self.paused = False
        self.root.after(150, self._drain_events)

    def _go_back(self) -> None:
        transitions = {
            "welcome": self.show_language_page,
            "browser": self.show_welcome,
            "extension": self.show_browser_page,
            "vortex": self.show_extension_page,
        }
        callback = transitions.get(self.page)
        if callback:
            callback()

    def _on_close(self) -> None:
        if self.runner and self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_NAME, self.t("close_confirm")):
                return
            self.runner.stop()
        self.root.destroy()


def main() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
