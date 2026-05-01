import sys
import colorama
import subprocess
from pathlib import Path

import pymake_cfg as cfg


TARGET = Path(cfg.OUT_DIR) / cfg.NAME
OBJ_DIR = Path(cfg.OUT_DIR)


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"{colorama.Style.DIM}{' '.join(cmd)}{colorama.Style.RESET_ALL}")
    return subprocess.run(cmd, shell=True, check=True)


def _print_err(exit_code: int, message: str, flag_exit: bool = True) -> None:
    print(f"{colorama.Fore.RED}{message}{colorama.Style.RESET_ALL}")

    if flag_exit:
        sys.exit(exit_code)


class ProjectBuilder:
    def __init__(self, flag_clean: bool) -> None:
        out_dir = Path(cfg.OUT_DIR)
        src_dir = Path(cfg.SRC_DIR)

        if flag_clean:
            out_dir.rmdir()

        if not out_dir.exists():
            out_dir.mkdir()

        if not src_dir.exists():
            _print_err(1, f"Source directory `{src_dir}` not found")

        self.sources = [
            Path(source)
            for source in src_dir.iterdir()
            if source.suffix in [".c", ".cc", ".cpp", ".c++", ".cxx"]
        ]

        self.exec_cmd = [cfg.CC, f"-std={cfg.STANDARD}"]
        self.exec_cmd.extend([f"-I{inc_dir}" for inc_dir in cfg.INC_DIRS])
        self.exec_cmd.extend([f"-D{define}" for define in cfg.DEFINES])
        self.exec_cmd.extend([f"-L{lib_dir}" for lib_dir in cfg.LIB_DIRS])
        self.exec_cmd.extend([f"-l{library}" for library in cfg.LIBRARIES])

    def _compile_source(self, source: Path) -> Path:
        obj_path = OBJ_DIR / source.stem

        cmd_result = _run_cmd(
            [*self.exec_cmd, "-c", str(source), "-o", str(obj_path) + ".o"]
        )

        if cmd_result.returncode != 0:
            _print_err(
                cmd_result.returncode, f"Failed to compile `{source}` -> `{obj_path}`"
            )

        return obj_path.with_suffix(".o")

    def build(self) -> None:
        if not self.sources:
            _print_err(1, "No sources found")

        objects = [
            str(self._compile_source(source))
            for source in self.sources
        ]

        cmd_result = _run_cmd(
            [*self.exec_cmd, *objects, "-o", str(TARGET)]
        )

        if cmd_result.returncode != 0:
            _print_err(cmd_result.returncode, "Failed to link")


if __name__ == "__main__":
    colorama.init(autoreset=True)
    ProjectBuilder(False).build()
