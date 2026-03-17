from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from aiohttp.web import Application


class BaseAccessor:
    def __init__(self, app: Application) -> None:
        self.app = app
        app.on_startup.append(self.connect)
        app.on_cleanup.append(self.disconnect)

    async def connect(self, app: Application) -> None:
        pass

    async def disconnect(self, app: Application) -> None:
        pass
