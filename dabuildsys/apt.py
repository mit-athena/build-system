#!/usr/bin/python

"""
Classes related to reading the APT repository.
"""

#
# The following is the terminology I attempt to stick to
# in the following code:
# * release -- release of Debian or Ubuntu we are building for ('wheezy' or 'trusty')
# * pocket -- production (''), proposed, development, staging, bleeding
# * distribution -- tuple of release and pocket
# * component -- same as in sources.list(5) ('debathena', 'debathena-config', etc)
#

import config
from checkout import PackageCheckout
from common import BuildError

from debian.debian_support import Version
from collections import defaultdict
import debian.deb822
import glob
import os.path

class APTFile(object):
    """A file in the APT repository."""

    def __init__(self, name, basedir, sha256):
        self.name = name
        self.path = os.path.join(basedir, name)
        self.sha256 = sha256

class APTSourcePackage(object):
    def __init__(self, name, version, architecture):
        self.name = name
        self.version = Version(version)
        self.architecture = architecture

    def __str__(self):
        return "%s=%s" % (self.name, self.version)

    def __repr__(self):
        return str(self)

class APTBinaryPackage(object):
    def __init__(self, name, version, architecture):
        self.name = name
        self.architecture = architecture

        # We do not need ~ubuntu-version suffix here
        self.full_version = version
        if '~' in version:
            self.version = Version(version.split('~')[0])
        else:
            self.version = Version(version)

    def __str__(self):
        return "%s:%s=%s" % (self.name, self.architecture, self.version)

    def __repr__(self):
        return str(self)

class APTDistribution(object):
    def __init__(self, name):
        if isinstance(name, tuple):
            self.release, self.pocket = name
            name = '-'.join(name) if name[1] != '' else name[0]
        else:
            self.release, self.pocket = name.split('-') if '-' in name else (name, '')

        self.name = name
        self.path = os.path.join(config.apt_root_dir, 'dists', name)
        self.load_sources()
        self.load_binaries()

    def load_sources(self):
        self.sources = {}
        for sources_file_path in glob.glob(os.path.join(self.path, '*', 'source',  'Sources')):
            with open(sources_file_path, 'r') as sources_file:
                for source_pkg in debian.deb822.Sources.iter_paragraphs(sources_file):
                    pkg = APTSourcePackage(source_pkg['Package'], source_pkg['Version'], source_pkg['Architecture'])
                    basedir = os.path.join(config.apt_root_dir, source_pkg['Directory'])
                    pkg.files = [APTFile(f['name'], basedir, f['sha256']) for f in source_pkg['Checksums-Sha256']]
                    self.sources[pkg.name] = pkg

    def load_binaries(self):
        self.binaries = defaultdict(dict)
        for packages_file_path in glob.glob(os.path.join(self.path, '*', 'binary-*', 'Packages')):
            with open(packages_file_path, 'r') as packages_file:
                for binary_pkg in debian.deb822.Packages.iter_paragraphs(packages_file):
                    pkg = APTBinaryPackage(binary_pkg['Package'], binary_pkg['Version'], binary_pkg['Architecture'])
                    path = os.path.join(config.apt_root_dir, binary_pkg['Filename'])
                    pkg.file = APTFile(os.path.basename(path), path, binary_pkg['SHA256'])
                    self.binaries[pkg.name][pkg.architecture] = pkg

    def merge(self, other):
        """Adds the packages from other distribution, as long as they do not
        override the newer packages in current."""

        for name, pkg_other in other.sources.iteritems():
            pkg_cur = self.sources.get(name)
            if not pkg_cur or pkg_cur.version < pkg_other.version:
                self.sources[name] = pkg_other

        for name, pkgs_other in other.binaries.iteritems():
            for arch, pkg_other in pkgs_other.iteritems():
                pkg_cur = self.binaries.get(name)
                if pkg_cur:
                    pkg_cur = pkg_cur.get(arch)
                    if not pkg_cur or pkg_cur.version < pkg_other.version:
                        self.binaries[name][arch] = pkg_other
                else:
                    self.binaries[name] = {}
                    self.binaries[name][arch] = pkg_other

def get_release(distribution):
    """For given release, returns (production, proposed, development)
    tuple of distributions."""

    production = APTDistribution(distribution)
    proposed = APTDistribution( (distribution, 'proposed') )
    development = APTDistribution( (distribution, 'development') )
    proposed.merge(production)
    development.merge(proposed)
    return (production, proposed, development)

def compare_against_git(apt_repo, update_all=False, checkout_cache=None):
    """Compare particular APT repo against the state of repositories in Git.
    If update_all is set to true, the repositories are fetched and reset to
    remote state.

    Returns a list of (package name, git version, APT version) tuples, where
    APT version is None if package is not in the repo, and git version is None
    if the checkout is invalid"""

    result = []
    use_cache = isinstance(checkout_cache, dict)
    for package in config.package_map:
        # Retrieve the checkout, possibly from cache, skip if invalid
        try:
            try:
                checkout = checkout_cache[package]
                if not checkout:
                    continue
            except:
                checkout = PackageCheckout(package, full_clean=update_all)
                if use_cache:
                    checkout_cache[package] = checkout
        except BuildError as err:
            result.append( (package, None, err) )
            if use_cache:
                checkout_cache[package] = None
            continue

        if apt_repo.release not in checkout.get_supported_releases():
            continue

        apt_package = apt_repo.sources.get(checkout.name)
        if apt_package:
            if checkout.released_version_obj > apt_package.version:
                result.append( (checkout.name, checkout.released_version_obj, apt_package.version) )
        else:
            result.append( (checkout.name, checkout.released_version_obj, None) )

    return result
