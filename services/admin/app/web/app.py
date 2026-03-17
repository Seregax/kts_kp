from __future__ import annotations

import base64
import hashlib

from aiohttp.web import (
    Application as AiohttpApplication,
    Request as AiohttpRequest,
    View as AiohttpView,
)
from aiohttp_session import setup as setup_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from app.store import Store
from app.web.config import Config, setup_config
from app.web.middlewares import auth_middleware
from app.web.routes import setup_routes
from shared.db.database import Database


class Application(AiohttpApplication):
    config: Config
    store: Store
    database: Database


class Request(AiohttpRequest):
    @property
    def app(self) -> Application:
        return super().app


class View(AiohttpView):
    @property
    def request(self) -> Request:
        return super().request

    @property
    def store(self) -> Store:
        return self.request.app.store

    @property
    def database(self) -> Database:
        return self.request.app.database


async def _connect_db(app: Application) -> None:
    await app.database.connect(app.config.database.dsn)


async def _disconnect_db(app: Application) -> None:
    await app.database.disconnect()


def setup_app(config_path: str) -> Application:
    app = Application(middlewares=[auth_middleware])
    app.config = setup_config(config_path)
    app.database = Database()
    app.on_startup.append(_connect_db)
    app.on_cleanup.append(_disconnect_db)
    app.store = Store(app)

    key_bytes = hashlib.sha256(app.config.session.key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    setup_session(app, EncryptedCookieStorage(fernet_key))

    setup_routes(app)
    return app
