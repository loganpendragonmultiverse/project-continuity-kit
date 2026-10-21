"""Frozen public-tag Windows QA transport; no source or release mutation."""

import hashlib
import io
import json
import os
import platform
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = "loganpendragonmultiverse/project-continuity-kit"
COMMIT = "a148c2853aad298e8b4bb65acc4e85d119c2f627"
RUN = 39542805129
ARTIFACT = 12319858628
ENVELOPE = "05770467ca4aa468ad3ede520607edb70a2aa7c115e5e12333524a4dc7749265"
RUNNER = "a89e5bbb2cf419f6b103dbd3a10c0d1e8a85caad73c1b38f0a3609d2ec5a1870"
ROUTING = "88c56213b0961010188bec0a218a5f3d5fa80c28d7df8f63b0b1290cfce08caa"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gh(path):
    r = subprocess.run(["gh", "api", "--method", "GET", path], check=False, capture_output=True)
    if r.returncode:
        raise RuntimeError("Read-only official artifact request failed")
    return r.stdout


def write(path, data):
    with path.open("xb") as f:
        f.write(data)


def inputs():
    assert sha((HERE / "run_continuity_native.py.txt").read_bytes()) == RUNNER
    raw = (HERE / "routing.json").read_bytes()
    assert sha(raw) == ROUTING
    c = json.loads(raw)
    assert c["commit"] == COMMIT and c["tag_run"] == RUN
    return c


def materialize_source(source, c, root):
    """Use exact committed bytes before acceptance, without Git configuration edits."""

    def regular(path):
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
        for parent in path.parents:
            metadata = parent.lstat()
            assert stat.S_ISDIR(metadata.st_mode)
            assert not stat.S_ISLNK(metadata.st_mode)
            assert not getattr(metadata, "st_file_attributes", 0) & 0x400
        return info

    names = c["source_files"]
    assert len(names) == 40
    tracked = subprocess.run(
        ["git", "-C", str(source), "ls-tree", "-r", "--name-only", "-z", COMMIT],
        capture_output=True,
        check=True,
    ).stdout
    assert {n.decode("utf-8") for n in tracked.split(b"\0") if n} == set(names)
    index = source / ".git/index"
    regular(index)
    index_hash = sha(index.read_bytes())
    blobs = {}
    initial = {}
    for name, digest in names.items():
        assert name and not name.startswith("/") and "\\" not in name and ":" not in name
        assert all(part not in {"", ".", ".."} for part in name.split("/"))
        selected = source.joinpath(*name.split("/"))
        regular(selected)
        raw = subprocess.run(
            ["git", "-C", str(source), "show", COMMIT + ":" + name],
            capture_output=True,
            check=True,
        ).stdout
        assert sha(raw) == digest
        blobs[name] = raw
        initial[name] = sha(selected.read_bytes())
    rows = []
    for name, raw in blobs.items():
        selected = source.joinpath(*name.split("/"))
        before = regular(selected)
        if initial[name] != sha(raw):
            flags = os.O_WRONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(selected, flags)
            with os.fdopen(descriptor, "wb") as stream:
                opened = os.fstat(stream.fileno())
                assert stat.S_ISREG(opened.st_mode)
                assert (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino)
                stream.truncate(0)
                stream.write(raw)
                stream.flush()
        regular(selected)
        assert sha(selected.read_bytes()) == names[name]
        rows.append(
            {
                "name": name,
                "git_blob_sha256": names[name],
                "before_worktree_sha256": initial[name],
                "after_worktree_sha256": sha(selected.read_bytes()),
                "materialized": initial[name] != names[name],
            }
        )
    assert sha(index.read_bytes()) == index_hash
    write(
        root / "MATERIALIZATION.json",
        json.dumps(
            {
                "commit": COMMIT,
                "files": rows,
                "git_index_sha256": index_hash,
                "git_objects_index_configuration_unchanged": True,
                "passed": True,
                "scope": "Ephemeral exact-tag checkout bytes materialized from verified Git blobs before immutable acceptance; no source archive/copy or settings changes.",
            },
            indent=2,
        ).encode(),
    )


def main():
    mode = sys.argv[1]
    assert mode in {"download", "run"}
    assert platform.system() == "Windows" and sys.version_info[:2] in {(3, 10), (3, 14)}
    c = inputs()
    root = Path(os.environ["RUNNER_TEMP"]) / ("continuity-native-" + str(sys.version_info.minor))
    artifacts = root / "artifacts"
    if mode == "download":
        assert not root.exists()
        root.mkdir()
        artifacts.mkdir()
        meta = json.loads(gh(f"repos/{REPO}/actions/artifacts/{ARTIFACT}"))
        assert meta["id"] == ARTIFACT and (not meta["expired"]) and (meta["size_in_bytes"] == 67493)
        assert meta["digest"] == "sha256:" + ENVELOPE
        assert meta["workflow_run"]["id"] == RUN and meta["workflow_run"]["head_sha"] == COMMIT
        run = json.loads(gh(f"repos/{REPO}/actions/runs/{RUN}"))
        assert (
            run["head_sha"] == COMMIT
            and run["head_branch"] == "v1.4.2"
            and (run["event"] == "push")
        )
        assert (
            run["path"] == ".github/workflows/release.yml"
            and run["status"] == "completed"
            and (run["conclusion"] == "success")
        )
        raw = gh(f"repos/{REPO}/actions/artifacts/{ARTIFACT}/zip")
        assert len(raw) == 67493 and sha(raw) == ENVELOPE
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries = z.infolist()
            assert len(entries) == 3 and {i.filename for i in entries} == set(
                c["tag_artifact_hashes"]
            )
            assert all(
                not i.is_dir() and (not i.flag_bits & 1) and (i.file_size < 1000000)
                for i in entries
            )
            for i in entries:
                data = z.read(i)
                assert sha(data) == c["tag_artifact_hashes"][i.filename]
                write(artifacts / i.filename, data)
        write(
            root / "DOWNLOAD.json",
            json.dumps(
                {
                    "artifact_id": ARTIFACT,
                    "tag_run": RUN,
                    "commit": COMMIT,
                    "container_size": len(raw),
                    "container_sha256": sha(raw),
                    "asset_hashes": c["tag_artifact_hashes"],
                    "passed": True,
                },
                indent=2,
            ).encode(),
        )
    else:
        assert not os.environ.get("GH_TOKEN") and (not os.environ.get("GITHUB_TOKEN"))
        source = Path(os.environ["GITHUB_WORKSPACE"]) / "tag-source"
        r = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert r.stdout.strip() == COMMIT
        materialize_source(source, c, root)
        for n, h in c["source_files"].items():
            assert sha((source / n).read_bytes()) == h, n
        for n, h in c["tag_artifact_hashes"].items():
            assert sha((artifacts / n).read_bytes()) == h, n
        pre = root / "preflight"
        assert not pre.exists()
        pre.mkdir()
        target = pre / "target"
        target.mkdir()
        (target / "value.txt").write_text("native fixture", encoding="utf-8")
        (pre / "os-symlink").symlink_to(target, target_is_directory=True)
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(pre / "junction"), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert (pre / "os-symlink/value.txt").read_text() == "native fixture" and (
            pre / "junction/value.txt"
        ).read_text() == "native fixture"
        write(
            root / "PREFLIGHT.json",
            json.dumps(
                {
                    "system": platform.system(),
                    "platform": platform.platform(),
                    "python": sys.version,
                    "os_symlink": True,
                    "junction": True,
                    "runner_sha256": RUNNER,
                    "routing_sha256": ROUTING,
                    "source_files_sha256": c["source_files_sha256"],
                    "passed": True,
                },
                indent=2,
            ).encode(),
        )
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(HERE / "run_continuity_native.py.txt"),
                "--source",
                str(source),
                "--artifacts",
                str(artifacts),
                "--routing",
                str(HERE / "routing.json"),
                "--output",
                str(root / "acceptance"),
            ],
            check=True,
        )
        inputs()
        for n, h in c["source_files"].items():
            assert sha((source / n).read_bytes()) == h, n
        for n, h in c["tag_artifact_hashes"].items():
            assert sha((artifacts / n).read_bytes()) == h, n


if __name__ == "__main__":
    main()
