import sys
import platform
import shutil
from enum import Enum
from pathlib import Path
from dataclasses import dataclass

from . import _log

VERSION: int = 2


class Compiler(Enum):
    GCC = "gcc"
    GXX = "g++"
    CLANG = "clang"
    CLANGXX = "clang++"
    MSVC = "cl"


@dataclass(frozen=True)
class _SysInfo:
    os: str = platform.system().lower()
    architecture: str = platform.machine().lower()
    library_ver: int = VERSION


_SYS_INFO = _SysInfo()


def is_64bit() -> bool:
    return sys.maxsize > 2**32


def is_windows() -> bool:
    return _SYS_INFO.os == "windows"


def is_linux() -> bool:
    return _SYS_INFO.os == "linux"


def is_macos() -> bool:
    return _SYS_INFO.os == "darwin"


def is_unix() -> bool:
    return is_linux() or is_macos()


def get_version() -> int:
    return VERSION


def get_architecture() -> str:
    return _SYS_INFO.architecture


@staticmethod
def get_default_parallel_jobs() -> int:
    import os
    try:
        cpu_count = os.cpu_count() or 4
        return max(1, cpu_count)
    except:
        return 4


class BuildMode(Enum):
    DEBUG = 0
    RELEASE = 1
    RUN = 2


@dataclass(frozen=True)
class BuildConfig:
    mode: BuildMode
    should_clean: bool = False
    should_run_after: bool = False
    run_args: list[str] | None = None

    def is_mode_release(self) -> bool:
        return self.mode == BuildMode.RELEASE

    def is_mode_debug(self) -> bool:
        return self.mode == BuildMode.DEBUG

    def is_mode_run(self) -> bool:
        return self.mode == BuildMode.RUN

    def should_run(self) -> bool:
        return self.is_mode_run() or self.should_run_after


@dataclass
class ProjectConfig:
    name: str = "app"
    cc: Compiler = Compiler.GXX
    standard: str = "c++23"
    cxx_flags: tuple[str, ...] = ("-Wall", "-Wextra", "-Wpedantic")
    src_dir: Path = Path("source")
    out_dir: Path = Path("build")
    inc_dirs: tuple[Path, ...] = (Path("include"),)
    lib_dirs: tuple[Path, ...] = (Path("external"),)
    libraries: tuple[str, ...] = ()
    defines: tuple[str, ...] = ()
    parallel: int = get_default_parallel_jobs()
    pch_header: Path | None = None

    def __post_init__(self) -> None:
        if shutil.which(self.cc.value) is None:
            _log.err(f"Compiler $B`{self.cc}`$0 not found.")

        self.out_dir.mkdir(parents=True, exist_ok=True)

        if not self.src_dir.exists():
            _log.err(f"Source directory $dir`{self.src_dir}`$0 not found")

        if self.pch_header is not None and not self.pch_header.exists():
            _log.err(f"Precompiled header $dir`{self.pch_header}`$0 not found")

        self.target = self.out_dir / f"{self.name}"

        if is_windows():
            self.target = self.target.with_suffix(".exe")

    def get_flags(self) -> tuple[str, ...]:
        return (
            str(self.cc),
            f"-std={self.standard}",
            *self.cxx_flags,
            *[f"-D{ddf}" for ddf in self.defines],
            *[f"-I{inc}" for inc in self.inc_dirs],
            *[f"-L{lld}" for lld in self.lib_dirs],
            *[f"-l{lib}" for lib in self.libraries],
        )
