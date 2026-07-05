import asyncio

from app.core.config import get_settings
from app.infrastructure.crusoe.client import CrusoeClient


async def main() -> None:
    for model_id in await CrusoeClient(get_settings()).list_models():
        print(model_id)


if __name__ == "__main__":
    asyncio.run(main())
