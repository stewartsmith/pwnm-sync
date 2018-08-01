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

Each mail message (i.e. patch) that's in patchwork gets a `patchwork` tag.
Additionally, they will get extra tags based on the state of the patch in
patchwork.

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

CONTRIBUTING
============

Send patches to stewart@linux.ibm.com or use a GitHub Pull request.

Please ensure all contributions follow Developer Certificate of Origin:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```
