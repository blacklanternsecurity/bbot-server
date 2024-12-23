# Database Helpers

The `db` folder contains comprehensive helpers for interacting with BBOT server's primary database, i.e. the asset database.

The difference between `db` and `event_store` is that `db` has fullly fleshed-out support for the primary database, complete with complex filtering, etc., while `event_store` supports various different databases, albeit at a simpler level. Event store may use helpers from `db`, but not vice versa.

This gives you flexibility in choosing your event store.
