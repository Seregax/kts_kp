import json

from aiohttp.web import Response


def json_response(data, status: int = 200) -> Response:
    return Response(
        status=status,
        content_type="application/json",
        body=json.dumps(data),
    )


def error_response(message: str, status: int = 400) -> Response:
    return json_response({"error": message}, status=status)
