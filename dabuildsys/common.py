#!/usr/bin/python

import config

from debian.debian_support import Version
import errno
import os

class BuildError(Exception):
    pass

def extract_upstream_version(version):
    if not isinstance(version, Version):
        version = Version(version)
    return version.upstream_version

def claim_lock():
    try:
        fd = os.open(config.lock_file_path, os.O_CREAT | os.O_EXCL)
        os.close(fd)
        return True
    except OSError as err:
        if err.errno == errno.EEXIST:
            return False
        else:
            raise

def release_lock():
    os.unlink(config.lock_file_path)
