from uuid import uuid4


class CommandSession:
    """Represents request-like state belonging to one Discord command."""

    def __init__(self) -> None:
        self.id = uuid4().hex[:8]
        self.closed = False

    def close(self) -> None:
        self.closed = True
