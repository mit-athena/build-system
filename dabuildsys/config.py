#!/usr/bin/python

"""
Shared configuration-level variables.
"""

from glob import glob
import os
import os.path

debian_releases = ['wheezy', 'jessie']
ubuntu_releases = ['precise', 'quantal', 'saucy', 'trusty']
releases = debian_releases + ubuntu_releases

debian_tags = { 'wheezy' : '7.0', 'jessie' : '8.0~0.1' }
ubuntu_tags = { 'precise' : '12.04', 'quantal' : '12.10', 'saucy' : '13.10' }

package_search_paths = ['athena/*', 'debathena/*', 'third/*']
package_root = os.environ['DEBATHENA_CHECKOUT_HOME']

package_paths = [ os.path.join(package_root, path) for path in package_search_paths ]
package_paths = sum(map(glob, package_paths), [])
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

# Arch on which all packages are built
all_arch = 'amd64'

source_package_dir = os.environ['DEBATHENA_SOURCE_DIR']
orig_tarball_dir = os.environ['DEBATHENA_ORIG_DIR']
apt_root_dir = os.environ['DEBATHENA_APT_DIR']
lock_file_path = os.environ['DEBATHENA_LOCK_FILE']

release_tag_key = "0D8A9E8F"
