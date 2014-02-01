#!/usr/bin/python

from debian.debian_support import Version

class BuildError(Exception):
    pass

def extract_upstream_version(version):
    if not isinstance(version, Version):
        version = Version(version)
    return version.upstream_version
