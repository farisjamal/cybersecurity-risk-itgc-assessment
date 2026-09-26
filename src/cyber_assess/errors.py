"""Domain errors with stable command-line exit semantics."""


class AssessmentError(Exception):
    """Base error for a failed assessment operation."""


class InvalidInputError(AssessmentError):
    """Input or canonical records are invalid (exit code 2)."""


class MissingPrerequisiteError(AssessmentError):
    """A runtime prerequisite is unavailable (exit code 3)."""


class IntegrityError(AssessmentError):
    """Content integrity or publication checks failed (exit code 4)."""
