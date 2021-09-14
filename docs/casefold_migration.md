# Migrating to case-insensitive email addresses

**Note: the operation described in this documentation is only needed if your server was
running a version of Sydent earlier than 2.4.0 at some point, and only needs to be run
once. If the first version of Sydent you have set up is 2.4.0 or later, or if you have
already run this operation, you don't need to do it again.**

In the past, the Matrix specification would consider email addresses as case-sensitive. This means
`alice@example.com` and `Alice@example.com` would be seen as two different email addresses
which could each be associated with a different Matrix user ID.

With [MSC2265](https://github.com/matrix-org/matrix-doc/pull/2265), the Matrix
specification was updated so that email addresses are considered without any case sensitivity (so the two
addresses mentioned in the previous paragraph would be considered as being one and the
same).

As of version 2.4.0, Sydent supports this change by processing each new association
without case sensitivity. However, some data might remain in the database from earlier
versions when Sydent would support multiple associations for a given email address (by
using variations of the same address with a different case). This means some addresses in
your identity server's database might not have been stored in a format that allows for
case-insensitive processing, or might have duplicate associations.

To correct this, Sydent 2.4.0 introduces a [script](https://github.com/matrix-org/sydent/blob/main/scripts/casefold_db.py)
that inspects an identity server's database and fixes it to be compatible with this change:

```
Usage: /path/to/sydent/scripts/casefold_db.py [--no-email] [--dry-run] /path/to/sydent.conf

Arguments:
    * --no-email: don't send out emails when deleting associations due to duplicates
    * --dry-run: don't update database rows and don't send out emails
```

If the script finds a duplicate (i.e. an email address with multiple associations), it
keeps the most recent association and deletes the others. If one or more of the Matrix
user IDs that are being dissociated don't match the one being kept, the script also sends an
email to the address to inform the user of the dissocation.

The default template for this email can be found [here](https://github.com/matrix-org/sydent/blob/main/res/matrix-org/migration_template.eml.j2)
and can be overriden by configuring a custom template directory (by changing the
`templates.path` configuration setting). The custom template must be named `migration_template.eml.j2`
(or `migration_template.eml` if not using Jinja 2 syntax), and will be given the Matrix
user ID being dissociated at render through the variable `mxid`.

This script is safe to run whilst Sydent is running.

If the script is not run, there may be associations in your database that can no
longer be looked up and duplicate associations may be registered.
