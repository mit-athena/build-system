#!/usr/bin/python

"""
Utility classes for working with Git.
"""

import os.path
import subprocess

def flip(t):
    a, b = t
    return b, a

class GitRepository(object):
    # Currently hard-coded, but the idea is to have enough flexibility to make
    # the class work with other remotes
    remote = 'origin'

    def __init__(self, root):
        self.root = root

    def cmd(self, *args, **kwargs):
        """Invoke a shell command in the specified repository."""

        cmd = list(args)
        return subprocess.check_output(cmd, stderr = subprocess.STDOUT, cwd = self.root, **kwargs).strip()

    def git(self, *args, **kwargs):
        """Invoke git(1) for the specified repository."""

        return self.cmd(*(('git',) + args), **kwargs)

    def get_refs(self):
        output = self.git('show-ref')
        lines = output.split("\n")
        lines = map(str.strip, lines)
        return dict(flip(line.split(" ", 2)) for line in lines if line)

    def has_branch(self, name, local_only = False):
        local_ref = 'refs/heads/%s' % name
        remote_ref = 'refs/remotes/%s/%s' % (self.remote, name)

        refs = self.get_refs()
        return local_ref in refs or (not local_only and remote_ref in refs)

    def get_rev(self, name):
        return GitCommit(self, self.git('rev-parse', name))

    def read_branch_head(self, name):
        return self.get_rev('refs/heads/%s' % name)

    def read_tag(self, name):
        return self.get_rev('refs/tags/%s' % name)

    def clean(self):
        self.git('clean', '-xfd')
        self.git('reset', '--hard')

    def remote_checkout(self, branch):
        self.clean()
        self.git('checkout', '-B', branch, '%s/%s' % (self.remote, branch))

    def get_common_ancestor(self, rev1, rev2):
        self.git('merge-base', rev1, rev2)

    def get_object_type(self, obj):
        return self.git('cat-file', '-t', obj).strip()

    def import_tarball(self, tarfile, rev):
        if isinstance(rev, GitCommit):
            rev = rev.hash

        self.cmd('pristine-tar', 'commit', tarfile, rev)

    def export_tarball(self, tarfile):
        self.cmd('pristine-tar', 'checkout', tarfile)

class GitCommit(object):
    def __init__(self, repo, name):
        self.repo = repo
        self.hash = repo.git('rev-parse', name)

        self.desc = repo.git('cat-file', 'commit', self.hash).strip()

        lines = self.desc.split("\n")
        seperator = lines.index('')
        fields = [line.split(' ', 1) for line in lines[0:seperator]]
        self.summary = "\n".join(lines[seperator+1:])

        self.tree, = (field[1] for field in fields if field[0] == 'tree')
        self.parents = [field[1] for field in fields if field[0] == 'parent']

    def checkout(self):
        self.repo.clean()
        self.repo.git('checkout', self.hash)

    def read_file(self, path):
        pathspec = "%s:%s" % (self.hash, path)
        return self.repo.git('cat-file', 'blob', pathspec)

    def file_exists(self, path):
        try:
            self.read_file(path)
        except subprocess.CalledProcessError:
            return False

        return True
