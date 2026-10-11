"""Safe domain failures shared by portal services and HTTP error mapping."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for safe domain failures."""


class NotFoundError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class LoginThrottledError(DomainError):
    pass
