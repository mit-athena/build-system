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
# I am not sure I am actually able to stick to it though...
# Why is the structure of this repository so complicated?
#

import config
from checkout import PackageCheckout
from common import BuildError

from debian.debian_support import Version
from collections import defaultdict
import debian.deb822
import glob
import gzip
import os.path
import re
import tarfile

class APTFile(object):
    """A file in the APT repository."""

    def __init__(self, name, basedir, sha256):
        self.name = name
        self.path = os.path.join(basedir, name)
        self.sha256 = sha256

class APTSourcePackage(object):
    def __init__(self, name, manifest):
        self.name = name
        self.version = Version(manifest['Version'])
        self.architecture = manifest['Architecture']
        self.binaries = manifest['Binary'].split(', ')
        self.manifest = manifest
        self.relations = manifest.relations
        self.format = manifest['Format']

    def __str__(self):
        return "%s=%s" % (self.name, self.version)

    def __repr__(self):
        return str(self)

    def get_control_file(self):
        """Extract control file from the source package."""

        controlname = "%s-%s/debian/control" % (self.name, str(self.version))
        if self.format.startswith('3.0'):
            if self.format == '3.0 (native)':
                tarname = "%s_%s.tar." % (self.name, str(self.version))
            elif self.format == '3.0 (quilt)':
                tarname = "%s_%s.debian.tar." % (self.name, str(self.version))
                controlname = "debian/control"
            else:
                raise BuildError("Package %s has unsupported format %s in archive" % (self.name, self.format))

            try:
                tarpath, = [f.path for f in self.files if f.name.startswith(tarname)]
            except ValueError:
                raise BuildError("File %s.{gz,bz2,xz} not found for package %s" % (tarname, self.name))

            with tarfile.open(tarpath, 'r:*') as tar:
                return list(debian.deb822.Deb822.iter_paragraphs(
                    tar.extractfile(controlname)  ))

        # FIXME: this code should be gone once 1.0 packages are gone
        # I still can't believe I actually wrote this
        elif self.format == '1.0':
            if len(self.files) == 2:
                try:
                    tarpath, = [f.path for f in self.files if f.name.endswith('.tar.gz')]
                except ValueError:
                    raise BuildError("Package %s has format 1.0 and does not seem to have the tarball" % self.name)

                with tarfile.open(tarpath, 'r:*') as tar:
                    return list(debian.deb822.Deb822.iter_paragraphs(
                        tar.extractfile(controlname)  ))
            else:
                diffname = "%s_%s.diff.gz" % (self.name, str(self.version))
                try:
                    diffpath, = [f.path for f in self.files if f.name == diffname]
                except ValueError:
                    raise BuildError("File %s not found for package %s" % (diffname, self.name))

                diff = gzip.open(diffpath, 'r')
                while True:
                    line = diff.readline().strip()
                    if line.startswith('--- ') and line.endswith('/debian/control'):
                        line = diff.readline().strip()
                        if not line.startswith('+++ '):
                            raise BuildError("Malformed debian diff in package " + self.name)

                        line = diff.readline()
                        match = re.match(r"@@ -0,0 \+1,(\d+) @@", line)
                        if not match:
                            raise BuildError("Malformed debian diff in package " + self.name)
                        number_of_lines = int(match.group(1))

                        lines = []
                        for i in range(number_of_lines):
                            lines.append(diff.readline()[1:])

                        return list(debian.deb822.Deb822.iter_paragraphs(lines))
        else:
            raise BuildError("Package %s has unsupported format %s in archive" % (self.name, self.format))

    def get_binary_architectures(self):
        """Returns the dictionary of binary packages to list of architectures
        for which those packages are built."""

        # See commit 47126733bb in dpkg.
        # Prior to May 15, 2011, dpkg did not output "Architecture: any all"
        # for packages which contained both any and all architectures.
        # Here I attempt to detect those buggy packages by asserting that
        # packages with Package-List (which was finally introduced on May 28
        # same year, though it kind of existed some time before).
        dpkg_bug = 'Package-List' not in self.manifest

        arches_naive = self.architecture.split(' ')
        if len(self.binaries) == 1:
            return { self.binaries[0] : arches_naive }
        if not dpkg_bug and arches_naive == ['all']:
            return { binary: arches_naive for binary in self.binaries }
        # "any" is unsafe because some of the binaries may have more
        # restrictive architectures

        # Actually, very limited number of packages gets here
        # Cache those which still do
        try:
            return self.cached_architectures
        except AttributeError:
            pass

        control = self.get_control_file()
        binaries = {}
        for package in control:
            if 'Source' in package:
                continue

            binaries[package['Package']] = package['Architecture'].split(' ')

        if set(binaries) != set(self.binaries):
            raise BuildError("Package %s has mismatching list of binaries in dsc and control file" % self.name)

        self.cached_architectures = binaries
        return binaries

class APTBinaryPackage(object):
    def __init__(self, name, version, architecture, manifest):
        self.name = name
        self.architecture = architecture

        # We do not need ~ubuntu-version suffix here
        self.full_version = version
        if '~' in version:
            self.version = Version(version.split('~')[0])
        else:
            self.version = Version(version)

        self.manifest = manifest
        self.relations = manifest.relations

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
                    pkg = APTSourcePackage(source_pkg['Package'], source_pkg)
                    pkg.origin = self.name
                    basedir = os.path.join(config.apt_root_dir, source_pkg['Directory'])
                    pkg.files = [APTFile(f['name'], basedir, f['sha256']) for f in source_pkg['Checksums-Sha256']]
                    self.sources[pkg.name] = pkg

    def load_binaries(self):
        self.binaries = defaultdict(dict)
        for packages_file_path in glob.glob(os.path.join(self.path, '*', 'binary-*', 'Packages')):
            with open(packages_file_path, 'r') as packages_file:
                for binary_pkg in debian.deb822.Packages.iter_paragraphs(packages_file):
                    pkg = APTBinaryPackage(binary_pkg['Package'], binary_pkg['Version'], binary_pkg['Architecture'], binary_pkg)
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

    def out_of_date_binaries(self, arch):
        """Find all packages for which there is a source package in the
        repository, but not a binary one for a given architecture.  Returns
        a list of source packages which need rebuilding."""

        result = []
        for name, src_pkg in self.sources.iteritems():
            out_of_date = False
            for binary, arches in src_pkg.get_binary_architectures().iteritems():
                # Handle cases when package is not meant to be built
                # in the given architecture
                if arch == 'all' and 'all' not in arches:
                    continue
                if arch != 'all' and not ('any' in arches or arch in arches):
                    continue

                # Package was never built
                if binary not in self.binaries:
                    out_of_date = True
                    break

                # Package was not built for this archictecture
                bin_pkgs = self.binaries[binary]
                if arch not in bin_pkgs:
                    out_of_date = True
                    break

                # Actually compare versions
                bin_pkg = bin_pkgs[arch]
                if bin_pkg.version > src_pkg.version:
                    # Circumvent edge cases of version comparison with manual-config packages
                    if not (name.startswith('debathena-manual-') and name.endswith('-config')):
                        raise BuildError("Package %s has version higher in binary than in source" % bin_pkg.name)
                if src_pkg.version > bin_pkg.version:
                    out_of_date = True
                    continue

            if out_of_date:
                result.append(name)

        return result

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
            except KeyError:
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
