"""
Shared pytest fixtures and helpers for esmini Python API tests.

Environment variables
---------------------
ESMINI_LIB_DIR        : directory containing libesminiLib.so / libesminiRMLib.so
                        (defaults to <repo>/esmini_libs/)
ESMINI_RESOURCE_PATH  : directory containing resources/ (xosc, xodr, ...)
                        (defaults to <repo>/resources/)
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)


def _lib_dir() -> str:
    return os.environ.get(
        "ESMINI_LIB_DIR",
        os.path.join(_REPO_ROOT, "esmini_libs"),
    )


def _resource_root() -> str:
    return os.environ.get(
        "ESMINI_RESOURCE_PATH",
        os.path.join(_REPO_ROOT, "resources"),
    )


def _lib_suffix() -> str:
    if sys.platform in ("linux", "linux2"):
        return ".so"
    if sys.platform == "darwin":
        return ".dylib"
    return ".dll"


def _lib_stem(name: str) -> str:
    if sys.platform == "win32":
        return os.path.join(_lib_dir(), f"{name}{_lib_suffix()}")
    return os.path.join(_lib_dir(), f"lib{name}{_lib_suffix()}")


# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------


def _se_lib_available() -> bool:
    return os.path.isfile(_lib_stem("esminiLib"))


def _rm_lib_available() -> bool:
    return os.path.isfile(_lib_stem("esminiRMLib"))


def _xodr_available(name: str) -> bool:
    return os.path.isfile(os.path.join(_resource_root(), "xodr", name))


def _xosc_available(name: str) -> bool:
    return os.path.isfile(os.path.join(_resource_root(), "xosc", name))


skip_no_se_lib = pytest.mark.skipif(
    not _se_lib_available(),
    reason=f"libesminiLib not found in {_lib_dir()} - set ESMINI_LIB_DIR",
)

skip_no_rm_lib = pytest.mark.skipif(
    not _rm_lib_available(),
    reason=f"libesminiRMLib not found in {_lib_dir()} - set ESMINI_LIB_DIR",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def lib_dir():
    return _lib_dir()


@pytest.fixture(scope="session")
def resource_root():
    return _resource_root()


@pytest.fixture(scope="session")
def straight_xodr(resource_root):
    path = os.path.join(resource_root, "xodr", "straight_500m.xodr")
    if not os.path.isfile(path):
        pytest.skip(f"ODR file not found: {path}")
    return path


@pytest.fixture(scope="session")
def signs_xodr(resource_root):
    path = os.path.join(resource_root, "xodr", "straight_500m_signs.xodr")
    if not os.path.isfile(path):
        pytest.skip(f"ODR file not found: {path}")
    return path


@pytest.fixture(scope="session")
def cut_in_xosc(resource_root):
    path = os.path.join(resource_root, "xosc", "cut-in_simple.xosc")
    if not os.path.isfile(path):
        pytest.skip(f"XOSC file not found: {path}")
    return path


@pytest.fixture(scope="session")
def acc_test_xosc(resource_root):
    path = os.path.join(resource_root, "xosc", "acc-test.xosc")
    if not os.path.isfile(path):
        pytest.skip(f"XOSC file not found: {path}")
    return path
