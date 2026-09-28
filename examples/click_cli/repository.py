from examples.click_cli.domain import User


class UserRepository:
    """A scoped repository representing one CLI unit of work."""

    def __init__(self) -> None:
        self._users = [
            User(1, "Ada"),
            User(2, "Grace"),
            User(3, "Linus", active=False),
        ]
        self.closed = False

    def list(self, *, active_only: bool) -> tuple[User, ...]:
        if active_only:
            return tuple(user for user in self._users if user.active)
        return tuple(self._users)

    def deactivate(self, user_id: int) -> User | None:
        for index, user in enumerate(self._users):
            if user.id == user_id:
                updated = User(user.id, user.name, active=False)
                self._users[index] = updated
                return updated
        return None

    def close(self) -> None:
        self.closed = True
