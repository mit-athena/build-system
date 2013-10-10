#!/usr/bin/python

from common import *
import config
import git

import sys

def get_repo_for_package(name):
    if name not in config.package_map:
        raise DebathenaBuildError("Cannot find package %s" % name)

    return git.GitRepository(config.package_map[name])
