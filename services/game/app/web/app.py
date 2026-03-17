from __future__ import annotations

from aiohttp.web import Application as AiohttpApplication

from app.store import Store
from app.web.config import Config, setup_config
from shared.db.database import Database


class Application(AiohttpApplication):
    config: Config
    store: Store
    database: Database


async def _connect_db(app: Application) -> None:
    await app.database.connect(app.config.database.dsn)


async def _disconnect_db(app: Application) -> None:
    await app.database.disconnect()


def setup_app(config_path: str) -> Application:
    app = Application()
    app.config = setup_config(config_path)
    app.database = Database()
    app.on_startup.append(_connect_db)
    app.on_cleanup.append(_disconnect_db)
    app.store = Store(app)
    return app
