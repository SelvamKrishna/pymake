import sys
import platform
import colorama
import subprocess
import shutil

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pymake_cfg as cfg


def _get_target() -> Path:
    target = Path(cfg.OUT_DIR) / cfg.NAME
    if platform.system() == "Windows":
        target = target.with_suffix(".exe")
    return target


TARGET = _get_target()
OBJ_DIR = Path(cfg.OUT_DIR)

flag_verbose = False


def _ansi_print(color: str, message: str, end: str = "\n") -> None:
    print(f"{color}{message}{colorama.Style.RESET_ALL}")


def _print_err(exit_code: int, message: str, flag_exit: bool = True) -> None:
    _ansi_print(colorama.Fore.RED, f"Error: {message}")

    if flag_exit:
        sys.exit(exit_code)


def _print_help_message() -> None:
    _ansi_print(colorama.Style.BRIGHT, f"PyMake v{cfg.VERSION}")
    _ansi_print(colorama.Style.BRIGHT, f"\nUsage:")
    print(f"    {sys.argv[0]} debug [flags]   => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Build with debug symbols")
    print(f"    {sys.argv[0]} release [flags] => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Build optimized")
    print(f"    {sys.argv[0]} run [args...]   => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Run binary")
    _ansi_print(colorama.Style.BRIGHT, f"\nFlags:")
    print(f"    --verbose | -v  => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Show commands")
    print(f"    --clean   | -c  => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Clean build first")
    print(f"    --run     | -r  => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Run after build")
    print(f"    --help    | -h  => ", end="")
    _ansi_print(colorama.Fore.BLUE, "Show this help")
    print("")
    sys.exit(0)


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    if flag_verbose:
        _ansi_print(colorama.Style.DIM, f"> {' '.join(str(c) for c in cmd)}")

    return subprocess.run(cmd, check=False)


class ProjectBuilder:
    def __init__(self, flag_clean: bool, is_mode_release: bool) -> None:
        out_dir = Path(cfg.OUT_DIR)
        src_dir = Path(cfg.SRC_DIR)

        if flag_clean and out_dir.exists():
            shutil.rmtree(out_dir)

        out_dir.mkdir(parents=True, exist_ok=True)

        if not src_dir.exists():
            _print_err(1, f"Source directory `{src_dir}` not found")

        self.sources = sorted(
            Path(source)
            for source in src_dir.rglob("*")
            if source.suffix in {".c", ".cc", ".cpp", ".c++", ".cxx"}
        )

        self.exec_cmd = [
            cfg.CC,
            f"-std={cfg.STANDARD}",
            *cfg.CXX_FLAGS,
        ]

        if is_mode_release:
            self.exec_cmd.extend(["-O2", "-DNDEBUG", "-s"])
        else:
            self.exec_cmd.append("-g")

        self.exec_cmd.extend(f"-I{inc_dir}" for inc_dir in cfg.INC_DIRS)
        self.exec_cmd.extend(f"-D{define}" for define in cfg.DEFINES)
        self.exec_cmd.extend(f"-L{lib_dir}" for lib_dir in cfg.LIB_DIRS)
        self.exec_cmd.extend(f"-l{library}" for library in cfg.LIBRARIES)

        self.mode = "release" if is_mode_release else "debug"

    def _check_source_recompile(self, source: Path, obj_path: Path) -> bool:
        if not obj_path.exists():
            return True
        return source.stat().st_mtime > obj_path.stat().st_mtime

    def _compile_source(self, source: Path) -> Path:
        obj_path = OBJ_DIR / \
            source.relative_to(Path(cfg.SRC_DIR)).with_suffix(".o")
        obj_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._check_source_recompile(source, obj_path):
            return obj_path

        cmd_result = _run_cmd(
            [*self.exec_cmd, "-c", str(source), "-o", str(obj_path)]
        )

        if cmd_result.returncode != 0:
            _print_err(cmd_result.returncode, f"Failed to compile `{source}`")

        return obj_path

    def build(self) -> None:
        if not self.sources:
            _print_err(1, "No sources found")

        objects = []
        with ThreadPoolExecutor(max_workers=cfg.PARALLEL) as pool:
            objects = list(pool.map(self._compile_source, self.sources))

        cmd_result = _run_cmd(
            [*self.exec_cmd, *[str(obj) for obj in objects], "-o", str(TARGET)]
        )

        if cmd_result.returncode != 0:
            _print_err(cmd_result.returncode, "Failed to link")

    @staticmethod
    def run(arguments: list[str] = []) -> None:
        if not TARGET.exists():
            _print_err(1, f"Target `{TARGET}` not found")

        try:
            subprocess.run([str(TARGET), *arguments])
        except KeyboardInterrupt:
            print()
            sys.exit(130)


def main() -> None:
    global flag_verbose

    if len(sys.argv) <= 1:
        _print_help_message()

    main_cmd = sys.argv[1].strip().lower()

    if main_cmd in ("--help", "-h"):
        _print_help_message()

    if main_cmd not in {"debug", "release", "run"}:
        _print_err(1, f"Unknown command `{main_cmd}`")

    if main_cmd == "run":
        ProjectBuilder.run(sys.argv[2:])
        sys.exit(0)

    flag_verbose = "--verbose" in sys.argv or "-v" in sys.argv
    flag_release = main_cmd == "release"
    flag_clean = flag_release or "--clean" in sys.argv or "-c" in sys.argv
    flag_run = "--run" in sys.argv or "-r" in sys.argv

    builder = ProjectBuilder(flag_clean, flag_release)
    builder.build()

    if flag_run:
        builder.run(sys.argv[2:])


if __name__ == "__main__":
    colorama.init(autoreset=True)
    main()
