NAME = "app"
VERSION = "1.0.0"

CC = "g++"
STANDARD = "c++23"
CXX_FLAGS = ["-Wall", "-Wextra", "-Wpedantic"]

SRC_DIR = "source"
OUT_DIR = "build"

INC_DIRS = ["include"]
LIB_DIRS = ["external"]

LIBRARIES = []
DEFINES = []

PARALLEL = 4
