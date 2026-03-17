from aiohttp.web import Application


def setup_routes(app: Application) -> None:
    from app.admin.routes import register_urls

    register_urls(app)
