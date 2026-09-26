# Database migrations

The baseline revision creates the bank-lab schema. Apply migrations with
`alembic upgrade head`; use a new forward migration for later production
changes rather than editing a deployed revision.
