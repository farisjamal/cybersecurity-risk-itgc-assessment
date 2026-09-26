# POL-06 — Backup creation and validation

Version: 1.0

Status: authored exercise criterion

A backup is created after each demonstration transaction batch. Every created backup must have its
content digest verified before use, and a corrupt or mismatched artifact must be rejected without
altering the target database.

This is a project-authored lab criterion, not a production resilience commitment.
