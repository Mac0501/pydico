from examples.click_cli.domain import User
from examples.click_cli.repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def list(self, *, active_only: bool = True) -> tuple[User, ...]:
        return self._repository.list(active_only=active_only)

    def deactivate(self, user_id: int) -> User | None:
        return self._repository.deactivate(user_id)
