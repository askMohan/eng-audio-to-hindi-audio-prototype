class ProviderError(Exception):
    code = "PROVIDER_ERROR"
    recoverable = True


class ProviderTimeout(ProviderError):
    code = "PROVIDER_TIMEOUT"


class UnknownProviderError(ProviderError):
    code = "UNKNOWN_PROVIDER"
    recoverable = False


class MissingProviderDependency(ProviderError):
    code = "MISSING_PROVIDER_DEPENDENCY"
    recoverable = False
