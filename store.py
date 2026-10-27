"""
One settings file next to the program: mt_config.json.

Sections: "settings" (the connection fields, the password only with «Запомнить
настройки»), "commands" (the 10 command drafts), "ui" (column widths / order),
"networks" (subnets scanned with «Скан»), "devices" (the device list).

Every write replaces the whole file atomically (temporary file + rename), so a
crash mid-write never leaves a broken file. The scanner and the viewer
(mikrotik_viewer.py) share this file, so a write first re-reads it and changes only
its own section: what the other program saved to the other sections is kept. The files of older versions
(settings.json, commands.json, devices.json, ui.json) are read once, moved into
it and deleted.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from typing import Any, Dict, Optional


def app_dir(module_file: str) -> str:
    """The folder with the program's data (mt_config.json, Backups, winbox.exe): next to
    the .exe in a compiled build (the temporary folder a single-file .exe unpacks to
    would lose everything), next to the .py file otherwise."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(module_file))


class ConfigStore:
    def __init__(self, path: str, legacy: Optional[Dict[str, str]] = None, logger=None,
                 fallback: Optional[list] = None) -> None:
        self.path = path
        self.logger = logger
        self.error = ""          # why the file could not be read (shown in the log)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        if not os.path.exists(path):
            # a build that kept the file somewhere else (e.g. inside the unpacked bundle)
            for other in fallback or []:
                if os.path.abspath(other) != os.path.abspath(path) and os.path.exists(other):
                    try:
                        shutil.copy2(other, path)
                    except OSError:
                        continue
                    break
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self._data = data if isinstance(data, dict) else {}
            except (OSError, ValueError) as exc:
                self.error = str(exc)
                # keep the unreadable file for the operator instead of overwriting it
                try:
                    os.replace(path, path + ".broken")
                except OSError:
                    pass
        elif legacy:
            self._migrate(legacy)

    def _migrate(self, legacy: Dict[str, str]) -> None:
        moved = []
        for section, old in legacy.items():
            if not os.path.exists(old):
                continue
            try:
                with open(old, encoding="utf-8") as fh:
                    self._data[section] = json.load(fh)
                moved.append(old)
            except (OSError, ValueError):
                continue   # a broken old file is left where it is
        if moved and self._write():
            for old in moved:
                try:
                    os.remove(old)
                except OSError:
                    pass

    def get(self, section: str, default=None):
        with self._lock:
            return self._data.get(section, default)

    def has(self, section: str) -> bool:
        with self._lock:
            return section in self._data

    def _disk(self) -> Dict[str, Any]:
        """The file as it is now (another program may have written to it)."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def set(self, section: str, value) -> bool:
        with self._lock:
            self._data = {**self._data, **self._disk(), section: value}
            return self._write()

    def remove(self, section: str) -> bool:
        with self._lock:
            if section not in self._data and section not in self._disk():
                return True
            self._data = {k: v for k, v in {**self._data, **self._disk()}.items() if k != section}
            return self._write()

    def _write(self) -> bool:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.error = str(exc)
            if self.logger:
                self.logger.warning("could not write %s: %s", self.path, exc)
            return False
