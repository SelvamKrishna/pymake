import shutil
import sys
from pathlib import Path
from typing import override, Callable, Any

from . import _log
from . import _cmd


class _IPackage:
    def __init__(self, path: Path, link: str) -> None:
        self.name = path.name
        self.path = path
        self.link = link

    def check(self) -> bool:
        return self.path.exists() and any(self.path.iterdir())

    def uninstall(self, suppress_warning: bool = False) -> None:
        if self.path.exists():
            shutil.rmtree(self.path)
            _log.info(
                f"Removed package $B{self.name}$0 from $file`{self.path}`$0")
        elif not suppress_warning:
            _log.warn(f"Package $B{self.name}$0 not found")

    def _install_impl(self) -> None:
        raise NotImplementedError("Subclasses must implement _install_impl")

    def install(self) -> None:
        self.uninstall(suppress_warning=True)
        self._install_impl()

    def ensure(self, mod_fn: Callable[[Path], Any] | None = None) -> None:
        if self.check():
            return

        self.install()

        if mod_fn is None:
            return

        mod_fn(self.path)


class GitHubPackage(_IPackage):
    def __init__(self, path: Path, link: str) -> None:
        super().__init__(path, link)

    @override
    def _install_impl(self) -> None:
        _log.info(f"Cloning $B{self.name}$0 from $link`{self.link}`$0...")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _cmd.call_cmd(
                ["git", "clone", "--depth", "1", self.link, str(self.path)])
            _log.info(f"Successfully cloned package $B{self.name}$0")
        except Exception as e:
            _log.err(f"Failed to clone package $B{self.name}$0: {e}")


class ArchivePackage(_IPackage):
    def __init__(self, path: Path, link: str) -> None:
        super().__init__(path, link)

    @staticmethod
    def __safe_extract_tar(tar_path: Path, extract_path: Path) -> None:
        import tarfile

        extract_path.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                member_path = extract_path / member.name
                try:
                    member_path.resolve().relative_to(extract_path.resolve())
                except ValueError:
                    raise Exception(
                        f"Attempted path traversal in tar file: {member.name}")
            tar.extractall(extract_path)

    @staticmethod
    def __safe_extract_zip(zip_path: Path, extract_path: Path) -> None:
        import zipfile

        extract_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                member_path = extract_path / member
                try:
                    member_path.resolve().relative_to(extract_path.resolve())
                except ValueError:
                    raise Exception(
                        f"Attempted path traversal in zip file: {member}")
            zip_ref.extractall(extract_path)

    @override
    def _install_impl(self) -> None:
        import tempfile

        _log.info(f"Extracting $B{self.name}$0 from `{self.link}`...")
        self.uninstall(True)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
                tmp_path = Path(tmp.name)
                _cmd.call_cmd(
                    ["curl", "-L", "--fail", self.link, "-o", str(tmp_path)])
                tmp_path.chmod(tmp_path.stat().st_mode | 0o111)

            temp_extract_dir = self.path.parent / f".temp_extract_{self.name}"
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            temp_extract_dir.mkdir(parents=True)

            if self.link.endswith((".tar.gz", ".tgz")):
                ArchivePackage.__safe_extract_tar(tmp_path, temp_extract_dir)
            elif self.link.endswith(".zip"):
                ArchivePackage.__safe_extract_zip(tmp_path, temp_extract_dir)
            else:
                shutil.move(str(tmp_path), str(self.path))
                _log.info(f"Successfully downloaded package $B{self.name}$0")
                return

            extracted_items = list(temp_extract_dir.iterdir())

            if not extracted_items:
                _log.warn(
                    f"Package $B{self.name}$0 does not contain any files")
                return

            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                extracted_dir = extracted_items[0]
                shutil.move(str(extracted_dir), str(self.path))
            else:
                self.path.mkdir(exist_ok=True)
                for item in extracted_items:
                    shutil.move(str(item), str(self.path / item.name))

            shutil.rmtree(temp_extract_dir)

            _log.info(f"Successfully extracted package $B{self.name}$0")

        except Exception as e:
            _log.err(f"Failed to extract package $B{self.name}$0: {e}")
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()


class WebPackage(_IPackage):
    def __init__(self, path: Path, link: str) -> None:
        super().__init__(path, link)

    @override
    def _install_impl(self) -> None:
        _log.info(f"Downloading $B{self.name}$0 from $link`{self.link}`$0...")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _cmd.call_cmd(
                ["curl", "-L", "--fail", self.link, "-o", str(self.path)])
            _log.info(f"Successfully downloaded package $B{self.name}$0")
        except Exception as e:
            _log.err(f"Failed to download package $B{self.name}$0: {e}")


class ManualPackage(_IPackage):
    def __init__(self, path: Path, link: str) -> None:
        super().__init__(path, link)

    @override
    def _install_impl(self) -> None:
        _log.warn(f"Please install package $B{self.name}$0 manually")
        _log.warn(f"Download from: $link{self.link}$0")
        _log.warn(f"Install to: $file{self.path.absolute()}$0")
        sys.exit(0)


class CustomPackage(_IPackage):
    def __init__(self, path: Path, install_cmd: str) -> None:
        super().__init__(path, install_cmd)

    @override
    def _install_impl(self) -> None:
        _log.info(f"Running custom install command for $B{self.name}$0...")
        try:
            _cmd.call_cmd_s(self.link)
            _log.info(f"Successfully installed package $B{self.name}$0")
        except Exception as e:
            _log.err(f"Failed to install package $B{self.name}$0: {e}")
