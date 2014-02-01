#!/usr/bin/python

"""
Class which represents the source checkout of a package.
"""

import config
import debian.changelog
import git
import subprocess

from common import BuildError, extract_upstream_version

class PackageCheckout(git.GitRepository):
    def __init__(self, package, full_clean = False):
        if package not in config.package_map:
            raise BuildError("Cannot find package %s" % package)

        super(PackageCheckout, self).__init__(config.package_map[package])

        if full_clean:
            self.git('fetch', '--all')
            self.full_clean()

        self.determine_type()
        self.load_changelog()

    def get_debian_file(self, filename):
        rev = git.GitCommit(self, 'master' if self.native else 'debian')
        return rev.read_file('debian/%s' % filename)

    def exists_debian_file(self, filename):
        rev = git.GitCommit(self, 'master' if self.native else 'debian')
        return rev.file_exists('debian/%s' % filename)

    def determine_type(self):
        self.native = not self.has_branch('debian')

        if self.native:
            self.validate_native()
        else:
            self.validate_quilt()

        self.validate_common()

    def full_clean(self):
        self.clean()
        self.remote_checkout('master')
        if self.has_branch('debian'):
            self.remote_checkout('debian')

    def validate_common(self):
        if not self.exists_debian_file('gbp.conf'):
            raise BuildError('Package does not contain gbp.conf')

    def validate_native(self):
        try:
            source_format = self.get_debian_file('source/format')
        except:
            raise BuildError('Package does not specify the source format')

        if source_format != '3.0 (native)':
            raise BuildError('Package source format is not native')

    def validate_quilt(self):
        if not self.has_branch('debian', local_only=True):
            self.remote_checkout('debian')

        try:
            source_format = self.get_debian_file('source/format')
        except:
            raise BuildError('Package does not specify the source format')

        if source_format != '3.0 (quilt)':
            raise BuildError('Package source format is not quilt')

    def load_changelog(self):
        log = debian.changelog.Changelog(self.get_debian_file('changelog'))

        self.name = log.package

        self.version = log.full_version
        self.upstream_version = log.upstream_version

        if log.distributions == 'unstable':
            self.released = True
            self.released_version = self.version
        elif log.distributions == 'UNRELEASED':
            for change in log:
                if change.distributions == 'unstable':
                    self.released = False
                    self.released_version = str(change.version)
                    break
            else:
                raise BuildError("The package has no released versions")
        else:
            raise BuildError("Invalid suite name: " + log.distributions)

    def get_build_revisions(self, upstream_version, version):
        """Given the upstream and the Debian version, find the appropriate
        Git revision for upstream and for Debian, check their relationship
        and return them as (upstream, debian) revision tuple."""

        if self.native:
            cur = master = self.get_rev('master')
        else:
            cur = self.get_rev('debian')
            master = self.get_rev('master')
        prev = None
        found = False
        while True:
            # Read the changelog of current revisions
            try:
                log = debian.changelog.Changelog(cur.read_file('debian/changelog'))
            except subprocess.CalledProcessError:
                if found:
                    break
                else:
                    return None

            # Check if the current revision is matching
            if log.distributions == 'unstable' and str(log.full_version) == version and log.upstream_version == upstream_version:
                    # Found the matching revision
                    found = True

            elif found:
                # We found the point at which the release was made
                break

            # Move to next parent revision
            prev = cur
            parents = cur.parents
            if len(parents) == 0:
                # Not found
                return None
            elif len(parents) == 1:
                cur = self.get_rev(parents[0])
            else:
                debian_parents = [rev for rev in map(self.get_rev, parents) if not rev < master]
                if len(debian_parents) != 1:
                    raise BuildError("Debian revision search breakdown at revision %s" % str(cur))
                cur = self.get_rev(debian_parents[0])

        # If we are here, it means that we are past the part of the history where
        # the version matched our search conditions
        deb_rev = prev
        if self.native:
            return deb_rev, deb_rev

        orig_rev = deb_rev & master
        tagged_rev = self.read_tag(upstream_version)
        if orig_rev != tagged_rev:
            raise BuildError("Version tagged as release %s is not merge"
                    "base of corresponding Debian package release" % upstream_version)

        return orig_rev, deb_rev

    def get_source_filenames(self, version=None, include_extra=False):
        """Returns a list of all files included in the source package for this
        package.  If version is not specified, current is used.  If include_extra
        is True, .changes and .build files are included."""

        if not version:
            version = self.version

        package_name = "%s_%s" % (self.name, version)
        extras = ["%s_source.build", "%s_source.changes"] if include_extra else []
        if self.native:
            return [s % package_name for s in ["%s.dsc", "%s.tar.gz" ] + extras]
        else:
            orig = "%s_%s.orig.tar.gz" % (self.name, extract_upstream_version(version))
            return [s % package_name for s in ["%s.dsc", "%s.debian.tar.gz"] + extras] + [orig]
