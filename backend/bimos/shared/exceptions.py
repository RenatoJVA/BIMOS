"""Custom exceptions for BIMOS."""


class BimosError(Exception):
    """Base exception for all BIMOS errors."""


class ConfigurationError(BimosError):
    """Raised when the environment or configuration is invalid."""


class PipelineError(BimosError):
    """Raised when a computational pipeline fails."""


class JobError(BimosError):
    """Raised when a job operation fails."""


class ResourceError(BimosError):
    """Raised when a required resource (binary, file, image) is unavailable."""


class SecurityError(BimosError):
    """Raised when a security validation fails."""
