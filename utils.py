import csv
import os
import subprocess
from typing import List, Optional

# Some OpenCRAVAT annotator columns (e.g. litvar_full's PMID lists, or other
# verbose fields across the 53 OC_ANNOTATORS) can exceed Python's default
# csv module field-size limit (131072 bytes), causing:
#   _csv.Error: field larger than field limit (131072)
# in ANY stage that reads these TSVs. Raised once here, at import time,
# since every stage imports something from this module.
csv.field_size_limit(2**31 - 1)


def mkdirs(*paths: str) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)


def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Thin wrapper so every stage logs exactly what it's executing."""
    print(f"[run] {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def fetch(url: str, dest: str, post_cmd: Optional[List[str]] = None, required: bool = True) -> bool:
    """Download url -> dest, skipping if dest already exists.

    Returns True on success (or already-present), False on failure.
    If required=False, a failure is logged and swallowed instead of raising
    — use for "nice to have" files so one disk-full/network blip doesn't
    kill the whole pipeline run.
    """
    if os.path.exists(dest):
        print(f"[skip] {dest} already exists")
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[download] {url} -> {dest}")
    try:
        run(["wget", "-q", "--continue", "-O", dest, url])
    except subprocess.CalledProcessError as e:
        msg = f"[fetch] FAILED ({e.returncode}) downloading {url} -> {dest}"
        if e.returncode == 3:
            msg += " — exit code 3 = file I/O error, almost always disk full. Check `df -h`."
        if required:
            raise
        print(msg + " — continuing (required=False)")
        if os.path.exists(dest):
            os.remove(dest)
        return False

    if post_cmd:
        try:
            run(post_cmd)
        except subprocess.CalledProcessError:
            if required:
                raise
            print(f"[fetch] post_cmd failed for {dest} — continuing (required=False)")
            return False
    return True
