#!/usr/bin/python

"""
Class which represents the source checkout of a package.
"""

import config
import debian.changelog
import debian.deb822
import git
import os.path
import subprocess

from common import BuildError, extract_upstream_version

class PackageCheckout(git.GitRepository):
    def __init__(self, package, full_clean = False):
        if package not in config.package_map:
            raise BuildError("Cannot find package %s" % package)

        super(PackageCheckout, self).__init__(config.package_map[package])
        self.dirname = package

        if full_clean:
            self.git('fetch', '--all')
            self.full_clean()

        self.determine_type()
        self.load_changelog()

    def get_debian_file(self, filename):
        rev = self.get_rev('master' if self.native else 'debian')
        return rev.read_file('debian/%s' % filename)

    def exists_debian_file(self, filename):
        rev = self.get_rev('master' if self.native else 'debian')
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
        text = self.get_debian_file('changelog')
        self.name, self.released, self.version_obj, self.released_version_obj = self.parse_changelog(text)
        self.version = str(self.version_obj)
        self.released_version = str(self.released_version_obj)
        self.upstream_version = self.version_obj.upstream_version

    @staticmethod
    def parse_changelog(text):
        log = debian.changelog.Changelog(text)

        if log.distributions == 'unstable':
            return log.package, True, log.version, log.version
        elif log.distributions == 'UNRELEASED':
            for change in log:
                if change.distributions == 'unstable':
                    return log.package, False, log.version, change.version
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

    def get_source_filenames(self, version=None, include_extra=False, include_manifest=False):
        """Returns a list of all files included in the source package for this
        package.  If version is not specified, current is used.  If include_extra
        is True, .changes and .build files are included."""

        if not version:
            version = self.version

        package_name = "%s_%s" % (self.name, version)
        extras = []
        if include_extra:
            extras += ["%s_source.build", "%s_source.changes"]
        if include_manifest:
            extras += ["%s.debathena"]
        if self.native:
            return [s % package_name for s in ["%s.dsc", "%s.tar.gz" ] + extras]
        else:
            orig = "%s_%s.orig.tar.gz" % (self.name, extract_upstream_version(version))
            return [s % package_name for s in ["%s.dsc", "%s.debian.tar.gz"] + extras] + [orig]

    def get_supported_releases(self):
        """Returns the list of releases for which package is still built."""

        # FIXME: this code should only parse the prologue of the file
        # Unfortunately, the fields in question were to this day only
        # specified for binary package, and extracted in a manner so
        # that field for any binary package affected all of them
        control = {}
        for block in debian.deb822.Deb822.iter_paragraphs(self.get_debian_file('control').split("\n")):
            control.update(block)

        releases = set(config.releases)
        if 'X-Debathena-Build-For' in control:
            releases &= set(control['X-Debathena-Build-For'].split(' '))

        if 'X-Debathena-No-Build' in control:
            releases -= set(control['X-Debathena-No-Build'].split(' '))

        return list(releases)

package_name_cache = {}

def lookup_by_package_name(name):
    global package_name_cache

    if not package_name_cache:
        for package_dirname, package_path in config.package_map.iteritems():
            repo = git.GitRepository(package_path)
            try:
                changelog_text = repo.git('cat-file', 'blob', 'refs/heads/debian:debian/changelog')
            except:
                try:
                    changelog_text = repo.git('cat-file', 'blob', 'refs/heads/master:debian/changelog')
                except:
                    continue
            package_name, _ = changelog_text.split(' ', 1)
            package_name_cache[package_name] = package_dirname

    return package_name_cache.get(name)
