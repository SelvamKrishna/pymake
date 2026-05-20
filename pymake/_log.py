import sys
import shutil
from typing import NoReturn
from pathlib import Path

from . import config

g_quiet: bool = False

_COLOR_ENABLED = sys.stdout.isatty()

_LUT: tuple[tuple[str, str], ...] = (
    ("$0", "\033[0m" if _COLOR_ENABLED else ""),
    ("$B", "\033[1m" if _COLOR_ENABLED else ""),
    ("$D", "\033[2m" if _COLOR_ENABLED else ""),
    ("$I", "\033[3m" if _COLOR_ENABLED else ""),
    ("$U", "\033[4m" if _COLOR_ENABLED else ""),
    ("$link", "\033[1;4m" if _COLOR_ENABLED else ""),
    ("$file", "\033[1;3m" if _COLOR_ENABLED else ""),
    ("$dir",  "\033[2;3m" if _COLOR_ENABLED else ""),
    ("$h1", "\033[4;34m" if _COLOR_ENABLED else ""),
)

_ERROR = f"\033[1;31m[ERROR:%d]\033[0m" if _COLOR_ENABLED else "[ERROR:%d]"
_WARNING = f"\033[1;33m[WARNING]\033[0m" if _COLOR_ENABLED else "[WARNING]"
_INFO = f"\033[1;32m[INFO]\033[0m" if _COLOR_ENABLED else "[INFO]"


def log(*args, **kwargs) -> None:
    text = " ".join(map(str, args))

    for (code, color) in _LUT:
        text = text.replace(code, color)

    print(text, **kwargs)
    print("\033[0m", end="", flush=True)


def print_version() -> None:
    log(f"$BPyMake v{config.VERSION}$0", end="\n")


def info(message: str) -> None:
    if not g_quiet:
        log(f"{_INFO}: {message}")


def warn(message: str) -> None:
    log(f"{_WARNING}: {message}")


def err(message: str, err_code: int = 1) -> NoReturn:
    log(f"{_ERROR % err_code}: {message}")
    sys.exit(err_code)


def _cmd(cmd: list[str]) -> None:
    if not g_quiet:
        log(f"$D> {' '.join(cmd)}$0")


def exit_or_continue(message: str) -> None:
    while True:
        warn(message)
        log("Do you want to EXIT... $B[Y/N]$0")
        res = input(": ").strip().lower()
        if res == 'y':
            sys.exit(0)
        if res == 'n':
            return
