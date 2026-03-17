import asyncio
import os

from app.web.app import setup_app

_DEFAULT_CONFIG = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "..",
    "..",
    "etc",
    "config.yaml",
)


async def main() -> None:
    app = setup_app(config_path=os.environ.get("CONFIGPATH", _DEFAULT_CONFIG))
    app.freeze()
    await app.startup()
    try:
        await asyncio.Event().wait()
    finally:
        await app.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
