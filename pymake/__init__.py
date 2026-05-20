from ._core import *
from . import _log


s_proj: Project | None = None


def init(projcfg: config.ProjectConfig, buildcfg: config.BuildConfig) -> None:
    global s_proj
    s_proj = Project(projcfg, buildcfg)

    _log.g_quiet = "--quiet" in sys.argv or "-q" in sys.argv


def build_project() -> None:
    global s_proj

    if s_proj is None:
        _log.err("$BPyMake$0 not initialized")
    else:
        s_proj.build()


def run_project() -> None:
    global s_proj

    if s_proj is None:
        _log.err("$BPyMake$0 not initialized")
    else:
        s_proj.run()


def remove_path(path: Path) -> None:
    if not path.exists():
        return

    if path.is_file():
        path.unlink()

    elif path.is_dir():
        path.rmdir() if len(list(path.iterdir())) == 0 else shutil.rmtree(path)

    _log.info(f"Removed $file`{path}`$0")


def copy_path(src: Path, dst: Path) -> None:
    _log.info(f"Copying $file`{src}`$0 to $file`{dst}`$0...")

    if not src.exists():
        _log.err(f"File $file`{src}`$0 does not exist")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst) if src.is_file() else shutil.copytree(src, dst)


def move_path(src: Path, dst: Path) -> None:
    _log.info(f"Moving $file`{src}`$0 to $file`{dst}`$0...")

    if not src.exists():
        _log.err(f"File $file`{src}`$0 does not exist")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)


if __name__ == "__main__":
    _log.print_version()
