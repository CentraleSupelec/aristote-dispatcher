import asyncio
import logging
import signal

from probes import prober
from rpc_server import rpc_server
from settings import settings


# === Set constants ===

CHECK_DELAY = 5


# === Initialize global variables ==

shutdown_signal = asyncio.Event()


# === Main function ===

async def main():   
    await rpc_server.connect()

    if settings.USE_PROBES: await prober.set_started()

    # WIP
    # async def check_rpc_connection():
    #     while not shutdown_signal.is_set():
    #         if not await rpc_server.check_connection():
    #             try:
    #                 await rpc_server.reconnect()
    #             except Exception as e:
    #                 logging.error(f"Failed to reconnect RPC client: {e}")
    #         await asyncio.sleep(CHECK_DELAY)

    # asyncio.create_task(check_rpc_connection())
    
    # Consumer is running until shutdown signal is received
    # Until then, all action occurs in the on_message_callback
    await shutdown_signal.wait()

    logging.debug("Closing RPC connection...")
    await rpc_server.close()
    logging.info("RPC disconnected")


# === Entry point ===

if __name__=="__main__":
    logging.info("Starting consumer")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown():
        logging.info("Shutting down consumer...")
        shutdown_signal.set()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    if settings.USE_PROBES: loop.run_until_complete(prober.setup())

    try:
        loop.run_until_complete(main())
    finally:
        if settings.USE_PROBES: loop.run_until_complete(prober.cleanup())
        loop.close()
