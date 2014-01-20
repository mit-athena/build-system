#!/usr/bin/python

"""
Class which represents the source checkout of a package.
"""

import config
import debian.changelog
import git

from common import BuildError

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
        versions = self.parse_changelog(log)
        if not versions:
            raise BuildError("The package has no released versions")

        self.released, self.version, self.upstream_version, self.released_version = versions
        self.name = log.package

    def parse_changelog(self, log):
        """Parse the debian/changelog file. Returns None if package was never released
        or (is_released, version, upstream_version, released_version) otherwise."""

        version = log.full_version
        upstream_version = log.upstream_version
        if log.distributions == 'unstable':
            return (True, version, upstream_version, version)
        elif log.distributions == 'UNRELEASED':
            for change in log:
                if change.distributions == 'unstable':
                    return (False, version, upstream_version, str(change.version))
            else:
                return None
        else:
            raise BuildError("Invalid suite name: " + log.distributions)
