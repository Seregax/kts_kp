from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp_session import get_session

from app.admin.schemas import (
    AdminLoginRequest,
    AdminResponse,
    GameStatsResponse,
    PlayerStatsItem,
    SettingsResponse,
    SettingsUpdateRequest,
)
from app.web.app import View
from app.web.utils import error_response, json_response


class LoginView(View):
    async def post(self):
        data = await self.request.json()
        req = AdminLoginRequest.model_validate(data)
        admin = await self.store.admins.get_by_email(req.email)
        if admin is None or not admin.check_password(req.password):
            return error_response("Invalid credentials", status=403)
        session = await get_session(self.request)
        session["uid"] = admin.id
        return json_response(AdminResponse.model_validate(admin).model_dump())


class CurrentView(View):
    async def get(self):
        admin = self.request.get("admin")
        if admin is None:
            raise HTTPUnauthorized
        return json_response(AdminResponse.model_validate(admin).model_dump())


class LogoutView(View):
    async def post(self):
        admin = self.request.get("admin")
        if admin is None:
            raise HTTPUnauthorized
        session = await get_session(self.request)
        session.invalidate()
        return json_response({})


class SettingsListView(View):
    async def get(self):
        admin = self.request.get("admin")
        if admin is None:
            raise HTTPUnauthorized
        settings = await self.store.game.get_all_settings()
        return json_response(
            [SettingsResponse.model_validate(s).model_dump() for s in settings]
        )


class SettingsUpdateView(View):
    async def post(self):
        admin = self.request.get("admin")
        if admin is None:
            raise HTTPUnauthorized
        data = await self.request.json()
        req = SettingsUpdateRequest.model_validate(data)
        settings = await self.store.game.upsert_settings(
            chat_id=req.chat_id,
            initial_balance=req.initial_balance,
            target_balance=req.target_balance,
            bet_amount=req.bet_amount,
        )
        return json_response(
            SettingsResponse.model_validate(settings).model_dump()
        )


class GameStatsView(View):
    async def get(self):
        admin = self.request.get("admin")
        if admin is None:
            raise HTTPUnauthorized
        stats = await self.store.game.get_game_stats()
        return json_response(GameStatsResponse(**stats).model_dump())


class PlayerStatsView(View):
    async def get(self):
        admin = self.request.get("admin")
        if admin is None:
            raise HTTPUnauthorized
        players = await self.store.game.get_player_stats()
        return json_response(
            [PlayerStatsItem(**p).model_dump() for p in players]
        )
