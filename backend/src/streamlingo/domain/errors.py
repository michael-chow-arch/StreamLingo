class ServiceFailure(Exception):
    """Safe, protocol-facing failure without model inputs or credentials."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
