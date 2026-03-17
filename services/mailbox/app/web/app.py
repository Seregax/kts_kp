from __future__ import annotations

from aiohttp.web import Application as AiohttpApplication

from app.store import Store
from app.web.config import Config, setup_config


class Application(AiohttpApplication):
    config: Config
    store: Store


def setup_app(config_path: str) -> Application:
    app = Application()
    app.config = setup_config(config_path)
    app.store = Store(app)
    return app
