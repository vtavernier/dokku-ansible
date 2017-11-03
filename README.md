# dokku-ansible

***Warning: this repository is still work in progress, do not rely on it
in production environments. Its API is not fixed yet.***

## Description

dokku-ansible is a set of Ansible tasks to use in a playbook in order
to manage a Dokku installation. The following dokku subcommands are
_at least partially_ implemented:

* dokku apps
* dokku config
* dokku domains
* dokku plugin
* dokku postgres
* dokku ps
* dokku ssh-keys
* dokku storage

Note that setting up dokku on the target host is the responsibility
of a play that should be executed prior to using any of the dokku-ansible
tasks.

## Copyright

Vincent Tavernier <vincent [dot] tavernier [at] gmail.com>

