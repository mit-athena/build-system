#!/usr/bin/python

"""
Code to normalize the source package name specifier into the actual packages.
Returns the package checkouts.
"""

from common import BuildError
import apt
import config
import checkout

def expand_srcname_spec(spec):
    """Parse a list of source packages on which the operation is to be performed.
    If some variant of 'all' is specified, comparison against packages currently
    APT repository is made and packages which have older version in APT than in Git
    are returned."""

    if len(spec) == 1 and spec[0] == '*':
        checkouts = []
        for pkg in config.package_map:
            try:
                checkouts.append(checkout.PackageCheckout(pkg))
            except Exception as e:
                pass
        return checkouts, {}
    elif len(spec) > 1 or not spec[0].startswith('all'):
        return [checkout.PackageCheckout(pkg) for pkg in spec], {}
    else:
        if spec[0] == 'all':
            releases = config.releases
        elif spec[0].startswith('all:'):
            releases = [spec[0].split(':')[1]]
        else:
            raise BuildError("Invalid all-package qualifier specified")

        cache = {}
        packages = set()
        repos = {}
        for release in releases:
            _, _, apt_repo = apt.get_release(release)
            repos[release] = apt_repo
            comparison = apt.compare_against_git(apt_repo, checkout_cache=cache)
            packages |= set(checkout.lookup_by_package_name(pkg) for pkg, gitver, aptver in comparison if gitver)

        return [cache[pkg] for pkg in packages], repos
