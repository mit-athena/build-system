#!/usr/bin/python

"""
Shared configuration-level variables.
"""

from glob import glob
import os
import os.path

# If you edit these releases and tags, please also update
# debian-versions.sh in scripts.git (checked out at /mit/debathena/bin).

debian_releases = ['wheezy', 'jessie', 'stretch']
ubuntu_releases = ['precise', 'trusty', 'xenial', 'artful', 'bionic']
releases = debian_releases + ubuntu_releases

debian_tags = {
    'wheezy' : 'debian7.0',
    'jessie' : 'debian8.0',
    'stretch' : 'debian9.0',
}
ubuntu_tags = {
	'precise' : 'ubuntu12.04',
	'trusty' : 'ubuntu14.04',
	'xenial' : 'ubuntu16.04',
	'artful' : 'ubuntu17.10',
	'bionic' : 'ubuntu18.04',
}
release_tags = dict(debian_tags.items() + ubuntu_tags.items())

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

release_arches = { release : [arch for arch in arches if arch_for_release(arch, release)] for release in releases }
# Arch on which all packages are built
all_arch = 'amd64'

source_package_dir = os.environ['DEBATHENA_SOURCE_DIR']
binary_package_dir = os.environ['DEBATHENA_BINARY_DIR']
orig_tarball_dir = os.environ['DEBATHENA_ORIG_DIR']
apt_root_dir = os.environ['DEBATHENA_APT_DIR']
lock_file_path = os.environ['DEBATHENA_LOCK_FILE']
setup_hook_path = os.environ['DEBATHENA_SETUP_HOOK']

upstream_tarball_chroot = 'upstream-tarball-area'

release_tag_key = "0D8A9E8F"
