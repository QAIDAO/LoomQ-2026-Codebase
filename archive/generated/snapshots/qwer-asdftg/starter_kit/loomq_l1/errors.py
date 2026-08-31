class LoomQError(Exception):
    pass


class QASMParseError(LoomQError):
    pass


class QASMSemanticError(LoomQError):
    pass


class ExpressionError(LoomQError):
    pass


class UnsupportedTargetError(LoomQError):
    pass


class DependencyUnavailableError(LoomQError):
    pass


class ProviderExecutionError(LoomQError):
    pass


class NormalizationError(LoomQError):
    pass


class CredentialError(LoomQError):
    pass
