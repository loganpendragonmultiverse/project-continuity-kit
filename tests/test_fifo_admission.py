"""Actual FIFO retargeting, isolated with a timeout so a regression cannot hang QA."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="actual POSIX FIFO admission")


@pytest.mark.parametrize("member", ["chunks"])
def test_retarget_to_fifo_is_refused_before_read(tmp_path, member):
    import importlib

    module = importlib.import_module("project_continuity_kit.filesystem")
    code = r"""
import importlib, os, stat, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
module=importlib.import_module(sys.argv[3]); member=sys.argv[4]
target=Path(sys.argv[1]); target.write_bytes(b'{"x":1}')
fifo=target.with_name("fifo"); os.mkfifo(fifo)
original_open=Path.open; original_descriptor=os.open; changed=False
def retarget(name):
    global changed
    if not changed and Path(name)==target:
        os.replace(fifo,target); changed=True
def path_open(self,*args,**kwargs):
    retarget(self)
    return original_open(self,*args,**kwargs)
def descriptor(name,flags,*args,**kwargs):
    retarget(name)
    return original_descriptor(name,flags,*args,**kwargs)
Path.open=path_open; os.open=descriptor
refused=False
try:
    if member=="chunks":list(module.chunks(target,100))
    else:getattr(module,member)(target)
except (OSError,ValueError):refused=True
assert changed and refused and stat.S_ISFIFO(target.lstat().st_mode)
print("actual FIFO retarget refused without reading")
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(tmp_path / "input"),
            str(Path(module.__file__).parent.parent),
            "project_continuity_kit.filesystem",
            member,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "without reading" in result.stdout
