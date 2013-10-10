#!/usr/bin/python

"""
Shared configuration-level variables.
"""

from glob import glob
import os
import os.path
import operator

debian_releases = ['squeeze', 'wheezy']
ubuntu_releases = ['precise', 'quantal', 'raring']

package_search_paths = ['athena/*', 'debathena/*', 'third/*']
package_root = os.environ['DEBATHENA_CHECKOUT_HOME']

package_paths = [ os.path.join(package_root, path) for path in package_search_paths ]
package_paths = reduce(operator.add, map(glob, package_paths))
package_map = { path.split('/')[-1] : path for path in package_paths }

arches = ['i386', 'amd64', 'armel', 'armhf', 'sparc']
builders = {
    'i386' : 'local',
    'amd64' : 'local',
    'armel' : 'hecatoncheires.mit.edu',
    'armhf' : 'hecatoncheires.mit.edu',
    'sparc' : 'package-fusion.mit.edu',
}
def arch_for_release(arch, release):
    "Check if we build the specified arch for given suite."

    # We currently don't have the infrastructure for others
    return arch == 'i386' or arch == 'amd64'

source_package_dir = os.environ['DEBATHENA_SOURCE_DIR']
orig_tarball_dir = os.environ['DEBATHENA_ORIG_DIR']
