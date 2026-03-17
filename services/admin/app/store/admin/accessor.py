from __future__ import annotations

import hashlib
import typing

from sqlalchemy import select

from shared.base.base_accessor import BaseAccessor
from shared.models.admin import Admin

if typing.TYPE_CHECKING:
    from aiohttp.web import Application


class AdminAccessor(BaseAccessor):
    async def connect(self, app: Application) -> None:
        await self._seed_admin()

    async def _seed_admin(self) -> None:
        email = self.app.config.admin.email
        password = self.app.config.admin.password
        if await self.get_by_email(email) is None:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            async with self.app.database.session() as session:
                admin = Admin(email=email, password_hash=password_hash)
                session.add(admin)
                await session.commit()

    async def get_by_email(self, email: str) -> Admin | None:
        async with self.app.database.session() as session:
            result = await session.execute(
                select(Admin).where(Admin.email == email)
            )
            return result.scalar_one_or_none()

    async def get_by_id(self, uid: int) -> Admin | None:
        async with self.app.database.session() as session:
            result = await session.execute(select(Admin).where(Admin.id == uid))
            return result.scalar_one_or_none()
