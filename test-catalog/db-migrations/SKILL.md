---
name: db-migrations
description: "Manage database schema migrations: versioned migrations, rollback strategies, data backfills, and zero-downtime schema changes."
metadata:
  hermes:
    category: database
---

# Database Migrations

## When to Use
When changing database schemas, adding columns, creating indexes, or backfilling data.

## Procedure
1. Create migration file with up/down functions
2. Test migration on a copy of production schema
3. For zero-downtime: add column → backfill → add constraint → remove old
4. Use transactional migrations where supported
5. Always include a rollback path
6. Verify with `migrate status` after applying
