from pathlib import Path

import pymake

DEV: bool = False

PROJ_CFG = pymake.ProjectConfig(
    name="pymake_test",
    src_dir=Path.cwd() / "source",
    out_dir=Path.cwd() / "build",
)

if __name__ == "__main__":
    assert pymake.VERSION == 1

    if DEV:
        BUILD_CFG = pymake.CLI.get_build_config()
    else:
        BUILD_CFG = pymake.BuildConfig(mode=pymake.BuildMode.RELEASE)

    pymake.init(verbose=BUILD_CFG.is_verbose)

    proj = pymake.Project(PROJ_CFG)
    proj.build(BUILD_CFG)

    if BUILD_CFG.should_run():
        proj.run(BUILD_CFG.run_args)
