import sys
import time
import platform
import subprocess
import shutil
import colorama

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

VERSION: int = 1
PLATFORM = platform.system()
SOURCE_EXTENSIONS: set = {".c", ".cc", ".cpp", ".c++", ".cxx"}


class BuildMode(Enum):
    DEBUG = 0,
    RELEASE = 1,
    RUN = 2


@dataclass(frozen=True)
class BuildConfig:
    mode: BuildMode
    should_clean: bool = False
    should_run_after: bool = False
    is_verbose: bool = False
    run_args: list[str] | None = None

    def is_mode_release(self) -> bool:
        return self.mode == BuildMode.RELEASE

    def is_mode_debug(self) -> bool:
        return self.mode == BuildMode.DEBUG

    def is_mode_run(self) -> bool:
        return self.mode == BuildMode.RUN

    def should_run(self) -> bool:
        return self.is_mode_run() or self.should_run_after


@dataclass(frozen=True)
class ProjectConfig:
    name: str = "app"
    cc: str = "g++"
    standard: str = "c++23"
    cxx_flags: tuple[str, ...] = ("-Wall", "-Wextra", "-Wpedantic")
    src_dir: Path = Path("source")
    out_dir: Path = Path("build")
    inc_dirs: tuple[Path, ...] = (Path("include"),)
    lib_dirs: tuple[Path, ...] = (Path("external"),)
    libraries: tuple[str, ...] = ()
    defines: tuple[str, ...] = ()
    parallel: int = 8

    def target(self) -> Path:
        target = self.out_dir / self.name
        return target if not PLATFORM == "Windows" else target.with_suffix(".o")


class Project:
    def __init__(self, cfg: ProjectConfig) -> None:
        self.cfg = cfg
        self.exec_cmd = [
            self.cfg.cc, f"-std={self.cfg.standard}", *self.cfg.cxx_flags
        ]

    @staticmethod
    def _needs_compile(src: Path, obj: Path) -> bool:
        # TODO: Add support for dependencies
        return not obj.exists() or src.stat().st_mtime > obj.stat().st_mtime

    def _collect_srcs(self) -> list[Path]:
        if not self.cfg.src_dir.exists():
            Log.err(f"Source directory `{self.cfg.src_dir}` does not exist")

        return sorted(
            path
            for path in self.cfg.src_dir.rglob("*")
            if path.suffix in SOURCE_EXTENSIONS
        )

    def _compile_srcs(self) -> list[Path]:
        def src_to_obj(src: Path):
            obj = self.cfg.out_dir / \
                src.relative_to(src.parent).with_suffix(".o")

            if not Project._needs_compile(src, obj):
                return obj

            result = _run_cmd([
                *self.exec_cmd,
                "-c", str(src.relative_to(Path.cwd())),
                "-o", str(obj.relative_to(Path.cwd()))
            ])

            if result.returncode != 0:
                Log.err(f"Failed to compile `{src}`", result.returncode)

            return obj

        srcs = self._collect_srcs()

        with ThreadPoolExecutor(max_workers=self.cfg.parallel) as pool:
            objects = list(pool.map(src_to_obj, srcs))

        return objects

    def _link(self, objs: list[Path]) -> None:
        obj_str = [str(obj.relative_to(Path.cwd())) for obj in objs]

        result = _run_cmd([
            *self.exec_cmd, *
            obj_str, "-o", str(self.cfg.target().relative_to(Path.cwd()))
        ])

        if result.returncode != 0:
            Log.err("Failed to link", result.returncode)

    def build(self, build_cfg: BuildConfig = BuildConfig(BuildMode.DEBUG)) -> None:
        if build_cfg.should_clean:
            shutil.rmtree(self.cfg.out_dir, ignore_errors=True)
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)

        if build_cfg.is_mode_release():
            self.exec_cmd.extend(["-O2", "-DNDEBUG", "-s"])
        else:
            self.exec_cmd.extend(["-O0", "-g"])

        self.exec_cmd.extend(f"-D{ddf}" for ddf in self.cfg.defines)
        self.exec_cmd.extend(f"-I{dir}" for dir in self.cfg.inc_dirs)
        self.exec_cmd.extend(f"-L{dir}" for dir in self.cfg.lib_dirs)
        self.exec_cmd.extend(f"-l{lib}" for lib in self.cfg.libraries)

        start = time.time()
        self._link(self._compile_srcs())
        Log.ok(f"Built {self.cfg.name} in {time.time() - start:.2f}s")

    def run(self, arguments: list[str] | None = None) -> None:
        if arguments is None:
            arguments = []

        target = self.cfg.target()

        if not target.exists():
            Log.err(f"Target `{target}` not found")
        try:
            _run_cmd([str(target), *arguments])
        except KeyboardInterrupt:
            print()
            sys.exit(130)


class CLI:
    @staticmethod
    def get_build_config() -> BuildConfig:
        if len(sys.argv) <= 1:
            CLI.print_help()
            sys.exit(0)

        match sys.argv[1].strip().lower():
            case "debug": mode = BuildMode.DEBUG
            case "release": mode = BuildMode.RELEASE
            case "run": mode = BuildMode.RUN
            case "--version" | "-v":
                Log.pymake()
                sys.exit(0)
            case _:
                CLI.print_help()
                sys.exit(0)

        return BuildConfig(
            mode,
            "--clean" in sys.argv or "-c" in sys.argv,
            "--run" in sys.argv or "-r" in sys.argv,
            "--verbose" in sys.argv or "-v" in sys.argv,
            sys.argv[2:] if mode == BuildMode.RUN else None
        )

    @staticmethod
    def print_help() -> None:
        def usage(cmd: str, desc: str) -> None:
            print(f"    {sys.argv[0]} {cmd:20}", end="")
            Log.print(colorama.Fore.BLUE, desc)

        def flag(flag: str, desc: str) -> None:
            print(f"    {flag:29}", end="")
            Log.print(colorama.Fore.BLUE, desc)

        Log.pymake()
        Log.print(colorama.Style.DIM, "=" * 80)
        Log.print(colorama.Style.BRIGHT, "Usage:")
        usage("[--help | -h]", "Show this help message")
        usage("debug [flags]", "Build with debug symbols")
        usage("release [flags]", "Build optimized")
        usage("run [...]", "Run binary with given arguments")
        Log.print(colorama.Style.DIM, "=" * 80)
        Log.print(colorama.Style.BRIGHT, "Flags:")
        flag("--verbose | -v", "Show commands")
        flag("--clean   | -c", "Clean build first")
        flag("--run     | -r", "Run after build")
        Log.print(colorama.Style.DIM, "=" * 80)


class Log:
    f_verbose = False

    @staticmethod
    def _wrap(color: str, message: str) -> str:
        return f"{color}{message}{colorama.Style.RESET_ALL}"

    @staticmethod
    def print(color: str, *args, **kwargs) -> None:
        print(color, end="")
        print(*args, **kwargs)
        print(colorama.Style.RESET_ALL, end="")

    @staticmethod
    def dbg(message: str) -> None:
        if Log.f_verbose:
            print(f"{Log._wrap(colorama.Fore.CYAN, "debug: ")}{message}")

    @staticmethod
    def err(message: str, err_code: int = 1) -> None:
        print(f"{Log._wrap(colorama.Fore.RED, "error: ")}{message}")
        sys.exit(err_code)

    @staticmethod
    def ok(message: str) -> None:
        if Log.f_verbose:
            print(f"{Log._wrap(colorama.Fore.GREEN, "ok: ")}{message}")

    @staticmethod
    def cmd(cmd: list[str]) -> None:
        if Log.f_verbose:
            command = " ".join(str(c) for c in cmd)
            print(f"{Log._wrap(colorama.Style.DIM, f"> {command}")}")

    @staticmethod
    def pymake() -> None:
        Log.print(colorama.Style.BRIGHT, f"PyMake v{VERSION}")
        Log.print(colorama.Fore.BLUE, f"Platform: ", end="")
        Log.print(f"{PLATFORM} {platform.release()}")
        Log.print(colorama.Fore.BLUE, f"Python: ", end="")
        Log.print(f"Python: {colorama.Fore.WHITE}{sys.version}")


def init(verbose: bool = False) -> None:
    colorama.init(autoreset=True)
    Log.f_verbose = verbose


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    Log.cmd(cmd)
    return subprocess.run(cmd, check=False)


if __name__ == "__main__":
    Log.pymake()
