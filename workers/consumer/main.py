import asyncio
import logging
import signal

from .exceptions import UnknownPriorityHandler, UnknownStrategy
from .metrics import wait_for_vllms
from .priority_handler.ignore_priority_handler import (
    IgnorePriorityHandler,
)
from .priority_handler.vllm_priority_handler import VllmPriorityHandler
from .probes import Prober
from .quality_of_service_policy.warning_log_policy import WarningLogPolicy
from .rpc_server import RPCServer
from .settings import settings
from .strategy.least_busy import LeastBusy
from .strategy.metrics_based_strategy import MetricsBasedStrategy
from .strategy.round_robin import RoundRobin
from .strategy.server_selection_strategy import ServerSelectionStrategy

VLLM_SERVERS = settings.VLLM_SERVERS
RABBITMQ_URL = settings.RABBITMQ_URL

ROUTING_STRATEGY = settings.ROUTING_STRATEGY
LEAST_BUSY = "least-busy"
ROUND_ROBIN = "round-robin"
IGNORE_PRIORITY_HANDLER = "ignore"
VLLM_PRIORITY_HANDLER = "vllm"
TIME_TO_FIRST_TOKEN_THRESHOLD = settings.TIME_TO_FIRST_TOKEN_THRESHOLD
METRICS_REFRESH_RATE = settings.METRICS_REFRESH_RATE
REFRESH_COUNT_PER_WINDOW = settings.REFRESH_COUNT_PER_WINDOW

shutdown_signal = asyncio.Event()


async def main_consumer(p_strategy: ServerSelectionStrategy, p_rpc_server: RPCServer):
    await wait_for_vllms(VLLM_SERVERS)

    await p_rpc_server.first_connect()

    # Consumer is running until shutdown signal is received
    # Until then, all action occurs in the on_message_callback
    # of the RPCServer class
    await shutdown_signal.wait()

    await p_rpc_server.close()

    # we need to explicitly stop monitoring
    if isinstance(p_strategy, MetricsBasedStrategy):
        await p_strategy.tracker.stop_monitor()


def shutdown():
    logging.info("Shutting down consumer...")
    shutdown_signal.set()


if __name__ == "__main__":
    logging.info("Starting consumer")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if ROUTING_STRATEGY == LEAST_BUSY:
        strategy = loop.run_until_complete(
            LeastBusy.create(
                VLLM_SERVERS,
                METRICS_REFRESH_RATE,
                REFRESH_COUNT_PER_WINDOW,
            )
        )  # monitoring starts via the LeastBusy create method, no need to explicitly start it here
    elif ROUTING_STRATEGY == ROUND_ROBIN:
        strategy = RoundRobin(VLLM_SERVERS)
    else:
        raise UnknownStrategy(ROUTING_STRATEGY)

    if settings.PRIORITY_HANDLER == IGNORE_PRIORITY_HANDLER:
        priority_handler = IgnorePriorityHandler(settings.BEST_PRIORITY)
    elif settings.PRIORITY_HANDLER == VLLM_PRIORITY_HANDLER:
        priority_handler = VllmPriorityHandler(settings.BEST_PRIORITY)
    else:
        raise UnknownPriorityHandler(settings.PRIORITY_HANDLER)

    quality_of_service_policy = WarningLogPolicy(TIME_TO_FIRST_TOKEN_THRESHOLD)

    rpc_server = RPCServer(
        url=RABBITMQ_URL,
        strategy=strategy,
        quality_of_service_policy=quality_of_service_policy,
        priority_handler=priority_handler,
    )

    prober = Prober(rpc_server)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    if settings.USE_PROBES:
        loop.run_until_complete(prober.setup())

    try:
        loop.run_until_complete(main_consumer(strategy, rpc_server))
    except Exception as e:
        logging.fatal("Consumer fatal error: %s", e)
        raise
    finally:
        if settings.USE_PROBES:
            loop.run_until_complete(prober.cleanup())
        loop.close()
