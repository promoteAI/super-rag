

import os
import tarfile
import zipfile
from typing import IO

import py7zr
import rarfile

SUPPORTED_COMPRESSED_EXTENSIONS = [
    ".zip",
    ".rar",
    ".r00",
    ".7z",
    ".tar",
    ".gz",
    ".xz",
    ".bz2",
    ".tar.gz",
    ".tar.xz",
    ".tar.bz2",
    ".tar.7z",
]


# TODO: streaming uncompressing
def uncompress(fileobj: IO[bytes], suffix: str, dest: str):
    if suffix == ".zip":
        with zipfile.ZipFile(fileobj, "r") as zf:
            for name in zf.namelist():
                try:
                    name_utf8 = name.encode("cp437").decode("utf-8")
                except Exception:
                    name_utf8 = name
                zf.extract(name, dest)
                if name_utf8 != name:
                    os.rename(os.path.join(dest, name), os.path.join(dest, name_utf8))
    elif suffix in [".rar", ".r00"]:
        with rarfile.RarFile(fileobj, "r") as rf:
            rf.extractall(dest)
    elif suffix == ".7z":
        with py7zr.SevenZipFile(fileobj, "r") as z7:
            z7.extractall(dest)
    elif suffix in [".tar", ".gz", ".xz", ".bz2", ".tar.gz", ".tar.xz", ".tar.bz2", ".tar.7z"]:
        with tarfile.open(fileobj=fileobj, mode="r:*") as tf:
            tf.extractall(dest)
    else:
        raise ValueError(f"Unsupported file format {suffix}")
