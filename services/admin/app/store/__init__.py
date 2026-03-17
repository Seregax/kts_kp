from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from aiohttp.web import Application


class Store:
    def __init__(self, app: Application) -> None:
        from app.store.admin.accessor import AdminAccessor
        from app.store.game.accessor import GameAccessor

        self.admins = AdminAccessor(app)
        self.game = GameAccessor(app)
