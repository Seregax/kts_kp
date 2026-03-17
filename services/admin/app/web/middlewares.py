from aiohttp.web import Request, StreamResponse, middleware
from aiohttp_session import get_session


@middleware
async def auth_middleware(request: Request, handler) -> StreamResponse:
    session = await get_session(request)
    uid = session.get("uid")
    request["admin"] = None
    if uid is not None:
        admin = await request.app.store.admins.get_by_id(uid)
        request["admin"] = admin
    return await handler(request)
