from __future__ import annotations

import ctypes
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue

logger = logging.getLogger("nexus-clicker")


@dataclass(frozen=True)
class RunnerConfig:
    poll_interval: float
    last_item_path: Path
    success_count_path: Path
    language: str = "en"


def normalize_file_identity(identity: str) -> str:
    title = re.sub(r"\s*\|\s*\d+\s*/\s*\d+\s*$", "", identity)
    return " ".join(title.split()).casefold()


def read_previous_item(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def reserve_previous_item(path: Path, identity: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(identity, encoding="utf-8")
    temporary.replace(path)


def read_success_count(path: Path) -> int:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return 0
    count = int(value)
    if count < 0:
        raise ValueError(f"Download count cannot be negative: {count}")
    return count


def write_success_count(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(str(count), encoding="utf-8")
    temporary.replace(path)


def find_download_button():
    """Find Vortex's "Download manually" button in any visible Vortex window.

    Windows are found by their Vortex.exe process, not by title, so other
    windows that mention Vortex (browser tabs, folders) are never touched.
    """
    import vortex
    from pywinauto import Desktop

    handles = vortex.visible_windows()
    if not handles:
        return None
    desktop = Desktop(backend="uia")
    matches = []
    for handle in handles:
        try:
            window = desktop.window(handle=handle).wrapper_object()
            buttons = window.descendants(control_type="Button")
        except Exception:
            continue
        matches.extend(
            button
            for button in buttons
            if (button.element_info.name or "").strip().casefold() == "download manually"
        )
    if len(matches) > 1:
        raise RuntimeError("Multiple Download manually buttons found; refusing an ambiguous click.")
    if not matches:
        return None

    button = matches[0]
    # Read the dialog's texts (mod name and queue position like "4/120").
    # Walk up a few levels so small layout changes in Vortex don't break it.
    labels: list[str] = []
    container = button
    for _ in range(4):
        container = container.parent() if container else None
        if container is None:
            break
        labels = [
            control.element_info.name.strip()
            for control in container.descendants(control_type="Text")
            if control.element_info.name and control.element_info.name.strip()
        ]
        if any(re.fullmatch(r"\d+\s*/\s*\d+", label) for label in labels):
            break
    position = next((s for s in labels if re.fullmatch(r"\d+\s*/\s*\d+", s)), None)
    title = next(
        (
            s for s in labels
            if s.casefold() != "download mod"
            and not re.fullmatch(r"\d+\s*/\s*\d+", s)
            and s.casefold() not in {"free", "premium", "by"}
        ),
        None,
    )
    if title and position:
        return button, f"{title}|{position.replace(' ', '')}"
    if labels:
        return button, " | ".join(labels)[:300]
    return None


def acquire_single_instance():
    if not hasattr(ctypes, "WinDLL"):
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, "Local\\NexusClicker.Desktop")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        raise RuntimeError("Nexus Clicker is already running.")
    return kernel32, handle


class DownloadRunner:
    def __init__(self, config: RunnerConfig, events: Queue[tuple[str, str]]) -> None:
        self.config = config
        self.events = events
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.language = config.language if config.language in {"en", "ru"} else "en"

    def stop(self) -> None:
        self.stop_event.set()
        self.pause_event.set()

    def pause(self) -> None:
        self.pause_event.clear()

    def resume(self) -> None:
        self.pause_event.set()

    def _emit(self, kind: str, message: str) -> None:
        self.events.put((kind, message))
        if kind == "log":
            logger.info(message)

    def _text(self, english: str, russian: str) -> str:
        return russian if self.language == "ru" else english

    def run(self) -> None:
        mutex = None
        failed = False
        try:
            mutex = acquire_single_instance()
            try:
                successful_actions = read_success_count(self.config.success_count_path)
            except (OSError, ValueError) as exc:
                logger.exception("Could not read the successful download count.")
                successful_actions = 0
                self._emit(
                    "log",
                    self._text(
                        f"Couldn't load the saved click count, starting from zero: {exc}",
                        f"Не удалось загрузить сохранённый счётчик, начинаем с нуля: {exc}",
                    ),
                )
            self._emit("download_count", str(successful_actions))
            scan_count = 0
            scan_error_count = 0
            last_health_emit = time.monotonic()
            self._emit("health", "0|0")
            self._emit(
                "status",
                self._text(
                    "Running. Waiting for the next mod in Vortex",
                    "Работает. Ждём следующий мод в Vortex",
                ),
            )
            self._emit(
                "log",
                self._text(
                    "Started. Watching Vortex for \"Download manually\".",
                    "Запущено. Следим за кнопкой «Download manually» в Vortex.",
                ),
            )
            while not self.stop_event.is_set():
                if not self.pause_event.wait(0.1):
                    continue
                scan_started = time.perf_counter()
                scan_count += 1
                try:
                    item = find_download_button()
                except Exception:
                    scan_error_count += 1
                    logger.exception("Vortex scan failed; will retry.")
                    self._emit(
                        "status",
                        self._text(
                            "Couldn't read Vortex, trying again",
                            "Не удалось прочитать Vortex, пробуем снова",
                        ),
                    )
                    now = time.monotonic()
                    if now - last_health_emit >= 5:
                        self._emit(
                            "health",
                            f"{scan_count}|{scan_error_count}",
                        )
                        last_health_emit = now
                    self.stop_event.wait(0.5)
                    continue
                now = time.monotonic()
                if now - last_health_emit >= 5:
                    self._emit(
                        "health",
                        f"{scan_count}|{scan_error_count}",
                    )
                    last_health_emit = now
                if item is None:
                    self.stop_event.wait(self.config.poll_interval)
                    continue

                button, raw_identity = item
                identity = normalize_file_identity(raw_identity)
                if not identity or identity == normalize_file_identity(
                    read_previous_item(self.config.last_item_path)
                ):
                    self.stop_event.wait(self.config.poll_interval)
                    continue

                self._emit(
                    "status",
                    self._text(f"Clicking: {raw_identity}", f"Нажимаем: {raw_identity}"),
                )
                if not self.pause_event.is_set():
                    self._emit(
                        "status",
                        self._text(
                            f"Paused before clicking: {raw_identity}",
                            f"Пауза перед нажатием: {raw_identity}",
                        ),
                    )
                    self.stop_event.wait(0.1)
                    continue
                reserve_previous_item(self.config.last_item_path, identity)
                try:
                    button.invoke()
                except Exception:
                    logger.exception("Could not invoke Download manually; retrying with the reserved item guard.")
                    self._emit(
                        "status",
                        self._text(
                            "Click failed, checking Vortex again",
                            "Не удалось нажать, проверяем Vortex снова",
                        ),
                    )
                    self.stop_event.wait(0.5)
                    continue

                elapsed = (time.perf_counter() - scan_started) * 1000
                self._emit(
                    "log",
                    self._text(
                        f"Clicked \"Download manually\": {identity} ({elapsed:.0f} ms)",
                        f"Нажато «Download manually»: {identity} ({elapsed:.0f} мс)",
                    ),
                )
                successful_actions += 1
                self._emit("download_count", str(successful_actions))
                try:
                    write_success_count(
                        self.config.success_count_path,
                        successful_actions,
                    )
                except OSError as exc:
                    logger.exception("Could not persist the successful download count.")
                    self._emit(
                        "log",
                        self._text(
                            f"Couldn't save the click count: {exc}",
                            f"Не удалось сохранить счётчик: {exc}",
                        ),
                    )
                self._emit(
                    "status",
                    self._text(
                        f"Waiting for the next mod (last: {identity})",
                        f"Ждём следующий мод (последний: {identity})",
                    ),
                )
                self.stop_event.wait(self.config.poll_interval)
        except Exception as exc:
            failed = True
            logger.exception("Runner stopped unexpectedly.")
            self._emit(
                "log",
                self._text(f"Error: {exc}", f"Ошибка: {exc}"),
            )
            self._emit(
                "status",
                self._text("Stopped after error", "Остановлено из-за ошибки"),
            )
        finally:
            if mutex:
                mutex[0].CloseHandle(mutex[1])
            if not failed:
                self._emit("status", self._text("Stopped", "Остановлено"))
