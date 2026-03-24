# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from io import BytesIO
import pathlib
import shutil
import tarfile

from cryptography.hazmat.primitives import hashes

def reset(tarinfo):
    tarinfo.mode = 0o644
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = "root"
    tarinfo.mtime = 1
    return tarinfo

def create_archive(folder_name, files=None):
    """
    Create a tar archive of the folder to take its secure hash.

    To make it reproducible, the files are listed and sorted.
    Furthermore, for the tar archive, the following changes are made:
    1) the user and group names are set to `root`,
    2) the `uid` and `gid` are set to 0,
    3) the file permissions are set to be 644 (-rw-r--r--), and
    4) the modification time is set to a constant value of 1.

    Returns the bytes buffer.
    """
    if not files:
        if folder_name[-1] != "/":
            folder_name += "/"

        # first, clean up, so that temporary files don't mess up our measurement values
        shutil.rmtree(folder_name + "__pycache__", ignore_errors=True)

        folder_path = pathlib.Path(folder_name)

        files = [str(file) for file in list(folder_path.rglob("*"))]
        files = sorted(files)

    print(files)

    archive_buffer = BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w", dereference=True) as tar:
        print("-- Archiving " + folder_name + " into buffer...")
        for fname in files:
            print(fname)
            tar.add(fname, arcname=fname[len(folder_name):], filter=reset)
            # tarinfo = tar.gettarinfo(name=fname, arcname=fname[len(folder_name):])
            # # ensure file permissions, gid, uid and modification time are the same
            # # for reproducibility of the hash of the archive
            # tarinfo.mode = 0o644
            # tarinfo.uid = tarinfo.gid = 0
            # tarinfo.uname = tarinfo.gname = "root"
            # tarinfo.mtime = 1
            # with open(fname, "rb") as f:
            #     tar.addfile(tarinfo, f)

    return archive_buffer

def compute_hash(data):
    """
    Compute the secure SHA-256 hash of data
    and return its hexadecimal value.
    """
    if not isinstance(data, bytes):
        data = bytes(data, "utf-8")

    hash_object = hashes.Hash(hashes.SHA256())
    hash_object.update(data)
    hash_value = hash_object.finalize().hex()

    return hash_value
