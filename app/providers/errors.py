"""Provider errors."""


class ProviderError(Exception):
    """Base provider failure."""


class ProviderConfigurationError(ProviderError):
    """Raised when no usable text provider is configured."""
