PatchWork NotMuch Sync!
=======================

This is a utility to synchronize patch status in patchwork to
tags in notmuch and back again.

The target audience is people working on projects that do patch
management in patchwork, and especially maintainers of said
projects.

Notmuch is the only mail client worth using, and patchwork is
part of the best way of doing software development.

All tags we care about have the 'pw-' prefix (for patchwork).
If you already use tags with this prefix, send a patch to fix
this software!

You will need:
 - A login to a patchwork instance
 - A patchwork instance with REST API support (i.e. patchwork 2.0+)
 - A REST API Token
 - A local notmuch database

My ~/.pwnm-sync.ini config file looks like:
```
[Defaults]
patchwork_token=abcdef1234567890
sync: skiboot=skiboot@lists.ozlabs.org,linuxppc-dev=linuxppc-dev@lists.ozlabs.org
```

This means I take the defaults for other config options (see --help),
such as where my notmuch database lives and the path to the sqlite3
database that helps maintain state for pwnm-sync.

Each patchwork project you sync gets a tag 'pw-{project}' to
signify that a mail is in the patchwork for that project. A
patch may be in multiple projects (e.g. a patch is CC'd to
several lists), and thus we maintain state for each project.

For example, when syncing the 'skiboot' project, I end up with
a bunch of notmuch tags like the following:
```
5 873 pw-skiboot
3 147 pw-skiboot-accepted
    9 pw-skiboot-awaiting-upstream
  389 pw-skiboot-changes-requested
    5 pw-skiboot-deferred
  104 pw-skiboot-new
  117 pw-skiboot-not-applicable
   77 pw-skiboot-rejected
  113 pw-skiboot-rfc
1 893 pw-skiboot-superseded
   19 pw-skiboot-under-review
```
The `pw-skiboot` tag tells me that a mail message is in the 'skiboot'
project in patchwork. If Patchwork knows about patches that my local
notmuch instance does not, then pwnm-sync will skip over them (and the
same the other way around).

If I am a maintainer on the skiboot project and I change which of the
'pw-skiboot-{state}' tags a message is tagged with, the next time
pwnm-sync is run, it'll update patchwork with the new status.

If you're not a maintainer and you change the state of a patch... something
will fail.

If you break the rules like putting multiple pw-{project}-{state} tags
for the same project, then err... something probably not great will happen.
PATCHES WELCOME.
