import sys
import time
import shutil
import subprocess

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import _cmd
from . import _log
from . import config

SOURCE_EXTENSIONS = {".cpp", ".c", ".cc", ".cxx", ".c++"}


class Project:
    def __init__(self, prjcfg: config.ProjectConfig, buildcfg: config.BuildConfig) -> None:
        self.prjcfg = prjcfg
        self.buildcfg: config.BuildConfig = buildcfg
        self._compile_cmd: list[str] = []
        self._link_cmd: list[str] = []
        self._pch_path: Path | None = None
        self._base_cmd: list[str] = [
            self.prjcfg.cc.value, f"-std={self.prjcfg.standard}"]

    def build(self) -> None:
        if self.buildcfg.is_mode_run():
            return

        if self.buildcfg.should_clean:
            self.__clean()

        self.__build_command(self.buildcfg.is_mode_release())
        self.__pch()

        start_time = time.time()
        objects = self.__compile_all()

        if not objects:
            _log.err("No object files generated")

        self._link(objects)
        elapsed = time.time() - start_time

        _log.info(f"Build successful! $B({elapsed:.2f}s)$0")

        if self.buildcfg.should_run_after:
            self.run(self.buildcfg.run_args)

    def __clean(self) -> None:
        try:
            if self.prjcfg.out_dir.exists():
                shutil.rmtree(self.prjcfg.out_dir)
                _log.info(f"$DCleaned `{self.prjcfg.out_dir}`$0")
            self.prjcfg.out_dir.mkdir(parents=True, exist_ok=True)

        except PermissionError as e:
            _log.err(
                f"Permission denied while cleaning: $file{e.filename}$0", err_code=126)

        except Exception as e:
            _log.err(f"Failed to clean directory: $dir{e}$0")

    def __build_command(self, is_release: bool) -> None:
        self._compile_cmd = self._base_cmd.copy()
        self._compile_cmd.extend(self.prjcfg.cxx_flags)

        if is_release:
            self._compile_cmd.extend(["-O2", "-DNDEBUG"])
            _log.info("Building in $h1RELEASE$0 mode")
        else:
            self._compile_cmd.extend(["-O0", "-g"])
            _log.info("Building in $h1DEBUG$0 mode")

        for define in self.prjcfg.defines:
            self._compile_cmd.append(f"-D{define}")

        for inc_dir in self.prjcfg.inc_dirs:
            self._compile_cmd.append(f"-I{inc_dir}")

        self._link_cmd = self._base_cmd.copy()

        for lib_dir in self.prjcfg.lib_dirs:
            self._link_cmd.append(f"-L{lib_dir}")

    def __pch(self) -> None:
        if self.prjcfg.pch_header is None or not self.prjcfg.pch_header.exists():
            return

        include_flag = f"-include{self.prjcfg.pch_header.stem}"
        pch_output = self.prjcfg.out_dir / \
            f"{self.prjcfg.pch_header.stem}.{"pch" if config.is_windows() else "gch"}"

        cmd = self._compile_cmd.copy() + [
            "-c", str(self.prjcfg.pch_header), "-o", str(pch_output)]

        try:
            _cmd.call_cmd(cmd, check=True)
            self._pch_path = pch_output
            _log.info(f"Precompiled header: $file{pch_output}$0")
            self._compile_cmd.append(include_flag)
        except Exception as e:
            _log.warn(
                f"Failed to precompile header: {e}, continuing without PCH")
            self._pch_path = None

    def __needs_compile(self, src: Path, obj: Path) -> bool:
        if not obj.exists():
            return True

        if src.stat().st_mtime > obj.stat().st_mtime:
            return True

        # TODO: Check header dependencies if you want more accurate tracking
        return False

    def __collect_srcs(self) -> list[Path]:
        if not self.prjcfg.src_dir.exists():
            _log.err(f"Source directory $dir`{self.prjcfg.src_dir}`$0 not found")
            return []

        srcs = [
            path for path in self.prjcfg.src_dir.rglob("*")
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS
        ]

        if not srcs:
            _log.err(f"No source files found in $dir{self.prjcfg.src_dir}$0")
            return []

        return sorted(srcs)

    def __compile_file(self, src: Path) -> Path | None:
        rel_path = src.relative_to(self.prjcfg.src_dir)
        obj = self.prjcfg.out_dir / rel_path.with_suffix(".o")
        obj.parent.mkdir(parents=True, exist_ok=True)

        if not self.__needs_compile(src, obj):
            _log.info(f"$D(up to date)$0 {src.name}")
            return obj

        cmd = self._compile_cmd.copy() + ["-c", str(src), "-o", str(obj)]

        try:
            _cmd.call_cmd(cmd, check=True)
            _log.info(f"Compiled: {src.name}")
            return obj
        except subprocess.CalledProcessError:
            _log.err(f"Failed to compile {src.name}")
        except Exception as e:
            _log.err(f"Failed to compile {src.name}: {e}")

    def __compile_all(self) -> list[Path]:
        sources = self.__collect_srcs()
        if not sources:
            return []

        _log.info(
            f"Compiling $B{len(sources)} file(s)$0 with $B{self.prjcfg.parallel} jobs$0")

        objects: list[Path] = []
        compiled_count = 0
        failed = False

        with ThreadPoolExecutor(max_workers=self.prjcfg.parallel) as executor:
            futures = {executor.submit(
                self.__compile_file, src): src for src in sources}

            for future in as_completed(futures):
                src = futures[future]
                try:
                    obj = future.result()
                    if obj is not None:
                        objects.append(obj)
                        compiled_count += 1
                    else:
                        failed = True
                except Exception as e:
                    _log.err(f"Exception compiling $file{src.name}$0: {e}")
                    failed = True

        if failed:
            _log.err("Compilation failed", 1)

        _log.info(
            f"Successfully compiled $B{compiled_count}/{len(sources)}$0 files")

        return objects

    def _link(self, objs: list[Path]) -> None:
        if not objs:
            _log.err("No object files to link")

        self.prjcfg.target.parent.mkdir(parents=True, exist_ok=True)

        link_cmd = self._link_cmd.copy()
        link_cmd.extend([str(obj) for obj in objs])

        for lib in self.prjcfg.libraries:
            link_cmd.append(f"-l{lib}")

        link_cmd.extend(["-o", str(self.prjcfg.target)])

        try:
            _cmd.call_cmd(link_cmd, check=True)
            if not config.is_windows():
                self.prjcfg.target.chmod(
                    self.prjcfg.target.stat().st_mode | 0o111)
            _log.info(f"Linked: $file{self.prjcfg.target}$0")
        except Exception as e:
            _log.err(f"Failed to link project $U{self.prjcfg.name}$0: {e}")

    def run(self, arguments: list[str] | None = None) -> None:
        if arguments is None:
            arguments = []

        if not self.prjcfg.target.exists():
            _log.err(
                f"Target $file`{self.prjcfg.target}`$0 not found. $DPlease build first.$0")

        _log.info(f"Running $file`{self.prjcfg.target}`$0")

        try:
            _cmd.call_cmd([str(self.prjcfg.target)] + arguments)
        except KeyboardInterrupt:
            print()
            _log.info("$DInterrupted by user$0")
            sys.exit(130)
        except Exception as e:
            _log.err(f"Failed to run executable: {e}")
