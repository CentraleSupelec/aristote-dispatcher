from aiohttp import web

from .rpc_server import rpc_server
from .settings import settings


class Prober:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get("/health", self.handle_health_check)
        self.app.router.add_get("/ready", self.handle_ready_check)
        self.runner = web.AppRunner(self.app)
        self.site = None

    async def setup(self):
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "0.0.0.0", settings.PROBE_PORT)
        await self.site.start()

    async def cleanup(self):
        await self.site.stop()
        await self.runner.cleanup()

    async def handle_health_check(self, request):
        # Consumer is self-healing, it is unhealthy only if it has crashed
        # It will then stop answering to health checks
        return web.Response(text="OK", status=200)

    async def handle_ready_check(self, request):
        # Consumer is ready when it is connected to RabbitMQ
        if rpc_server.check_connection():
            return web.Response(text="OK", status=200)
        else:
            return web.Response(text="NOK", status=503)


prober = Prober()
