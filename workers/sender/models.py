import time
from httpx import AsyncClient
from settings import Settings


models = []


async def get_models(settings: Settings):
    global models

    async with AsyncClient(base_url=settings.RABBITMQ_MANAGEMENT_URL) as http_client:
        response = await http_client.get(
            url=f"/api/exchanges/%2F/amq.default/bindings/source",
            auth=(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD),
        )
        response.raise_for_status()

    models = [
        {
            "id": binding["destination"],
            "object": "model",
            "owned_by": binding["destination"],
        }
        # We need to filter out the default entries of the default exchange
        for binding in response.json()
        if not binding["destination"].startswith("amq")
    ]

    return models


async def get_model_by_id(settings: Settings, id: str):
    global models

    model_ids = {model["id"] for model in models}

    if id not in model_ids:
        await get_models(settings)

    for model in models:
        if model["id"] == id:
            return model

    return None
