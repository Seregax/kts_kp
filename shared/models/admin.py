import hashlib

from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import BaseModel


class Admin(BaseModel):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)

    def check_password(self, password: str) -> bool:
        return (
            self.password_hash == hashlib.sha256(password.encode()).hexdigest()
        )
