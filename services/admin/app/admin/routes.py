from aiohttp.web import Application


def register_urls(app: Application) -> None:
    from app.admin.views import (
        CurrentView,
        GameStatsView,
        LoginView,
        LogoutView,
        PlayerStatsView,
        SettingsListView,
        SettingsUpdateView,
    )

    app.router.add_view("/admin.login", LoginView)
    app.router.add_view("/admin.current", CurrentView)
    app.router.add_view("/admin.logout", LogoutView)
    app.router.add_view("/settings.list", SettingsListView)
    app.router.add_view("/settings.update", SettingsUpdateView)
    app.router.add_view("/stats.games", GameStatsView)
    app.router.add_view("/stats.players", PlayerStatsView)
