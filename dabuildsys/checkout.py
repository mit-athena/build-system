#!/usr/bin/python

"""
Class which represents the source checkout of a package.
"""

import config
import git

class PackageCheckout(git.GitRepository):
    def __init__(self, package):
        if package not in config.package_map:
            raise DebathenaBuildError("Cannot find package %s" % package)

        super(PackageCheckout, self).__init__(config.package_map[package])
