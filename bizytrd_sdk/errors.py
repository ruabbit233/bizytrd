"""SDK-specific exceptions."""


class BizyTRDError(Exception):
    """Base SDK error."""


class BizyTRDPermissionError(BizyTRDError):
    """Authentication or permission failure."""


class BizyTRDConnectionError(BizyTRDError):
    """Network or transport failure."""


class BizyTRDResponseError(BizyTRDError):
    """Unexpected API response."""


class BizyTRDTimeoutError(BizyTRDError):
    """Polling timed out."""
