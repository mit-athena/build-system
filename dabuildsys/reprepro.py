#!/usr/bin/python

"""
Abstraction layer around reprepro.
"""

import config
from common import BuildError

from debian.debian_support import Version
from collections import defaultdict
import operator
import os
import re
import subprocess

def call(*args, **kwargs):
    """Invoke a shell command in the specified repository."""

    cmd = ['reprepro', '-V', '-b', config.apt_root_dir, '--ignore=wrongdistribution'] + list(args)
    return subprocess.check_output(cmd, stderr = subprocess.STDOUT, **kwargs).strip()

# FIXME: this thing is screenscrapping, and regex is awful
def list_package_versions(package):
    output = call('ls', package)
    regex = r"^%s\s+\|\s+(\S+)\s+\|\s+(\S+)\s+\|\s+([a-z0-9, ]+)$" % re.escape(package)
    matches = re.findall(regex, output, re.MULTILINE)
    if not matches and len(output) > 0:
        raise BuildError("Failed to parse `reprepro ls` output")
    versions = defaultdict(dict)
    for version, distribution, arches in matches:
        if 'bleeding' in distribution:
            continue
        arches = arches.split(', ')
        for arch in arches:
            versions[distribution][arch] = Version(version)

    return versions

def find_source_version(package, version):
    if not isinstance(version, Version):
        version = Version(version)

    versions = list_package_versions(package)
    # Do not just copy packages from random files, use some well-defined order
    order = versions.keys()
    order.sort(reverse=True)
    try:
        _, distro = min(reduce(operator.add, [
            [(order.index(distro), distro) for arch, ver in pkg.items() if arch == 'source' and ver == version]
            for distro, pkg in versions.iteritems()], []))
        return distro
    except ValueError:
        return None

def include_changes(distro, path):
    """Includes the package with specified changes file."""

    call('include', distro, path)

def include_package(distro, pkg, dver):
    """Include a package and version."""

    changes = "%s_%s_source.changes" % (pkg.name, dver)
    include_changes(distro, os.path.join(config.source_package_dir, changes))

def copy_package(pkg, from_dist, to_dist, export=True):
    """Copy a specific version of package (APTSourcePackage) from
    one distribution to another."""

    print call(*([] if export else ['--export=never']) +
               ['-A', 'source', 'copysrc', to_dist, from_dist, pkg.name, str(pkg.version)])
