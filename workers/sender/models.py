import time
from httpx import AsyncClient
from settings import Settings
import logging


models = []


async def get_models(settings: Settings):
    # TODO: ajouter le exchange name en variable d'env et l'utiliser ici et dans le RPCClient

    http_client = AsyncClient(base_url=settings.RABBITMQ_MANAGEMENT_URL)

    response = await http_client.get(
        url=f"/api/exchanges/%2F/rpc/bindings/source",
        auth=(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD),
    )

    global models
    models = [
        {
            "id": binding["destination"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": binding["destination"],
        }
        for binding in response.json()
    ]

    return models


async def get_model_by_id(settings: Settings, id: str):

    global models

    if id not in [model["id"] for model in models]:
        await get_models(settings)

    if id in [model["id"] for model in models]:
        return [model for model in models if model["id"] == id][0]

    return None
