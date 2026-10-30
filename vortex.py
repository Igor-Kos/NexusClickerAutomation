"""Find Vortex, check how it was started, and start it so its buttons are readable.

Vortex is identified only by its process name (Vortex.exe), never by window
titles or version-specific paths, so this keeps working across Vortex updates
and custom install folders.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

ACCESSIBILITY_FLAG = "--force-renderer-accessibility"
PROCESS_NAME = "vortex.exe"
CLOSE_TIMEOUT = 60
START_TIMEOUT = 90


class VortexError(RuntimeError):
    """A Vortex problem the app explains to the user. `code` picks the message."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class Process:
    pid: int
    parent_pid: int
    name: str


IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W))
    _kernel32.Process32FirstW.restype = wintypes.BOOL
    _kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W))
    _kernel32.Process32NextW.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _ntdll.NtQueryInformationProcess.argtypes = (
        wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG),
    )
    _ntdll.NtQueryInformationProcess.restype = wintypes.LONG
    _user32.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    _user32.GetWindow.restype = wintypes.HWND
    _user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _user32.PostMessageW.restype = wintypes.BOOL

_TH32CS_SNAPPROCESS = 0x00000002
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_COMMAND_LINE_INFORMATION = 60
_GW_OWNER = 4
_WM_CLOSE = 0x0010


def list_processes() -> list[Process]:
    if not IS_WINDOWS:
        return []
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    processes: list[Process] = []
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        more = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            processes.append(Process(entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
            more = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    return processes


def vortex_processes(processes: list[Process] | None = None) -> list[Process]:
    if processes is None:
        processes = list_processes()
    return [process for process in processes if process.name.casefold() == PROCESS_NAME]


def main_processes(processes: list[Process]) -> list[Process]:
    """Vortex is an Electron app: the main process is the Vortex.exe whose parent is not Vortex.exe."""
    pids = {process.pid for process in processes}
    mains = [process for process in processes if process.parent_pid not in pids]
    return mains or processes


def is_running() -> bool:
    return bool(vortex_processes())


def _open_process(pid: int):
    return _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)


def process_path(pid: int) -> Path | None:
    if not IS_WINDOWS:
        return None
    handle = _open_process(pid)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return Path(buffer.value)
    finally:
        _kernel32.CloseHandle(handle)


def process_command_line(pid: int) -> str | None:
    """Read another process's command line (Windows 8.1 and newer). None if it can't be read."""
    if not IS_WINDOWS:
        return None
    handle = _open_process(pid)
    if not handle:
        return None
    try:
        needed = wintypes.ULONG(0)
        _ntdll.NtQueryInformationProcess(handle, _PROCESS_COMMAND_LINE_INFORMATION, None, 0, ctypes.byref(needed))
        if not needed.value:
            return None
        buffer = ctypes.create_string_buffer(needed.value)
        status = _ntdll.NtQueryInformationProcess(
            handle, _PROCESS_COMMAND_LINE_INFORMATION, buffer, needed, ctypes.byref(needed),
        )
        if status != 0:
            return None
        text = ctypes.cast(buffer, ctypes.POINTER(_UNICODE_STRING)).contents
        if not text.Buffer:
            return None
        return ctypes.wstring_at(text.Buffer, text.Length // 2)
    finally:
        _kernel32.CloseHandle(handle)


def has_accessibility_flag(command_line: str) -> bool:
    return re.search(rf"(?:^|[\s\"]){re.escape(ACCESSIBILITY_FLAG)}(?:$|[\s\"=])", command_line) is not None


def visible_windows(main_only: bool = False) -> list[int]:
    """Handles of visible top-level windows that belong to Vortex processes."""
    if not IS_WINDOWS:
        return []
    processes = vortex_processes()
    if main_only:
        processes = main_processes(processes)
    pids = {process.pid for process in processes}
    if not pids:
        return []
    handles: list[int] = []

    def collect(hwnd, _lparam):
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.IsWindowVisible(hwnd):
            if not main_only or not _user32.GetWindow(hwnd, _GW_OWNER):
                handles.append(hwnd)
        return True

    _user32.EnumWindows(_WNDENUMPROC(collect), 0)
    return handles


def ui_has_buttons() -> bool:
    """Fallback check: Vortex exposes buttons to UI Automation only when accessibility is on."""
    from pywinauto import Desktop

    desktop = Desktop(backend="uia")
    for handle in visible_windows():
        try:
            if desktop.window(handle=handle).wrapper_object().descendants(control_type="Button"):
                return True
        except Exception:
            continue
    return False


def accessibility_state() -> str:
    """'not_running', 'ready', 'needs_restart', or 'unknown' when the command line can't be read."""
    processes = vortex_processes()
    if not processes:
        return "not_running"
    command_lines = [process_command_line(process.pid) for process in main_processes(processes)]
    known = [line for line in command_lines if line is not None]
    if not known:
        return "unknown"
    return "ready" if any(has_accessibility_flag(line) for line in known) else "needs_restart"


def _executable_from_command(value: str) -> Path | None:
    value = os.path.expandvars(str(value)).strip()
    match = re.match(r'^"([^"]+?\.exe)"', value, re.IGNORECASE) or re.match(
        r"^(.+?\.exe)(?=$|[\s,])", value, re.IGNORECASE
    )
    return Path(match.group(1)) if match else None


def _registry_candidates() -> list[Path]:
    if not IS_WINDOWS:
        return []
    import winreg

    def read(hive, subkey: str, name: str | None = None) -> str | None:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
                return str(value)
        except OSError:
            return None

    candidates: list[Path] = []
    # Vortex registers itself as the handler for nxm:// links (Mod Manager Download).
    for hive, subkey in (
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\nxm\shell\open\command"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes\nxm\shell\open\command"),
        (winreg.HKEY_CLASSES_ROOT, r"nxm\shell\open\command"),
    ):
        value = read(hive, subkey)
        path = _executable_from_command(value) if value else None
        if path:
            candidates.append(path)
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        value = read(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Vortex.exe")
        path = _executable_from_command(value) if value else None
        if path:
            candidates.append(path)
    # The installer's entry in Apps & features.
    for hive, subkey in (
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
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
                entry = f"{subkey}\\{child}"
                name = read(hive, entry, "DisplayName") or ""
                if not re.match(r"^\s*vortex\b", name, re.IGNORECASE):
                    continue
                location = read(hive, entry, "InstallLocation")
                if location:
                    candidates.append(Path(os.path.expandvars(location.strip().strip('"'))) / "Vortex.exe")
                icon = read(hive, entry, "DisplayIcon")
                path = _executable_from_command(icon) if icon else None
                if path:
                    candidates.append(path)
    return candidates


def _default_candidates() -> list[Path]:
    roots = [
        os.environ.get("ProgramW6432"),
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
    ]
    candidates = [Path(root) / "Black Tree Gaming Ltd" / "Vortex" / "Vortex.exe" for root in roots if root]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Vortex" / "Vortex.exe")
    return candidates


def find_executable() -> Path | None:
    candidates: list[Path] = []
    for process in main_processes(vortex_processes()):
        path = process_path(process.pid)
        if path:
            candidates.append(path)
    candidates += _registry_candidates() + _default_candidates()
    for path in candidates:
        if path.name.casefold() == PROCESS_NAME and path.is_file():
            return path
    return None


def close_gracefully(timeout: float = CLOSE_TIMEOUT) -> bool:
    """Ask Vortex to close like clicking X. Never force-kills. True once no Vortex.exe is left."""
    for handle in visible_windows(main_only=True):
        _user32.PostMessageW(handle, _WM_CLOSE, 0, 0)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_running():
            return True
        time.sleep(0.5)
    return not is_running()


def launch(executable: Path) -> None:
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(executable), ACCESSIBILITY_FLAG],
        cwd=str(executable.parent),
        close_fds=True,
        creationflags=flags,
    )


def start_with_accessibility(timeout: float = START_TIMEOUT) -> None:
    """Make sure Vortex runs with the accessibility flag: close it if needed, then start it."""
    if accessibility_state() == "ready":
        return
    executable = find_executable()
    if is_running() and not close_gracefully():
        raise VortexError("close_timeout")
    executable = executable or find_executable()
    if not executable:
        raise VortexError("not_found")
    launch(executable)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        state = accessibility_state()
        if state == "ready" and visible_windows(main_only=True):
            return
        if state == "unknown" and ui_has_buttons():
            return
    raise VortexError("start_timeout")
