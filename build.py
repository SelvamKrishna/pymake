import sys
from pathlib import Path

import pymake
import pymake.cli
import pymake.package

if pymake.config.is_windows():
    GLFW_LIB_DIR = Path("external/glfw/lib-mingw-w64")
    GLFW_LIB_NAME = "glfw3"
    ADDITIONAL_LIBS = (
        "opengl32", "gdi32", "winmm", "dwmapi", "ole32", "user32")

    pymake.package.ArchivePackage(
        path=Path("external/glfw"),
        link="https://github.com/glfw/glfw/releases/download/3.4/glfw-3.4.bin.WIN64.zip"
    ).ensure(
        lambda path: [
            pymake.remove_path(dir)
            for dir in path.iterdir()
            if dir.name.startswith("lib") and dir.name != "lib-mingw-w64" ])

else:
    raise OSError(f"Unsupported platform: {sys.platform}")


PROJ = pymake.config.ProjectConfig(
    name="opengl_app",
    standard="c++17",
    src_dir=Path("source"),
    inc_dirs=(
        Path("external/glfw/include"),
        Path("external/glad/include"),
    ),
    lib_dirs=(GLFW_LIB_DIR,),
    libraries=(GLFW_LIB_NAME,) + ADDITIONAL_LIBS,
)

pymake.package.CustomPackage(
    path=Path("external/glad"),
    install_cmd="glad --profile=core --api=gl=3.3 --generator=c --out-path=./external/glad"
).ensure(
    lambda path: [
        pymake.move_path(path / "src" / "glad.c", PROJ.src_dir / "glad.c"),
        pymake.remove_path(path / "src") ])


BUILD_CFG = pymake.cli.get_build_config()

if __name__ == "__main__":
    pymake.init(PROJ, BUILD_CFG)
    pymake.build_project()
