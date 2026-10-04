import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import config
from .api.routes import router
from .errors import ServiceError


def build_service():
    from .db import Database
    from .engine.executors import make_executor
    from .engine.service import Service

    db = Database(config.db_path())
    if config.use_fakes():
        from .fakes import FakeBank, FakeMarketData

        market_data, bank = FakeMarketData(), FakeBank()
    else:
        from .integrations.market_data import KalshiMarketData
        from .integrations.money import NessieBank

        market_data, bank = KalshiMarketData(config.kalshi_data_url()), NessieBank(db)
    executor = make_executor(config.hedge_mode(), market_data, config.MAX_CONTRACT_PRICE)
    return Service(db, market_data, bank, executor)


def _worker_loop(service, stop, interval):
    while not stop.is_set():
        try:
            service.run_settlement()
        except Exception as exc:  # the loop must outlive any single bad cycle
            service.last_result = f"error: {exc}"
        stop.wait(interval)


def create_app(service=None, worker=None):
    @asynccontextmanager
    async def lifespan(app):
        if app.state.service is None:
            app.state.service = build_service()
        stop = threading.Event()
        run_worker = config.worker_enabled() if worker is None else worker
        if run_worker:
            app.state.service.worker_enabled = True
            threading.Thread(
                target=_worker_loop,
                args=(app.state.service, stop, config.WORKER_INTERVAL_SECONDS),
                name="settlement-worker",
                daemon=True,
            ).start()
        yield
        stop.set()

    app = FastAPI(title="HedgeCast", version="2.0.0", lifespan=lifespan)
    app.state.service = service

    @app.exception_handler(ServiceError)
    def service_error(_request: Request, exc: ServiceError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    app.include_router(router)
    return app


app = create_app()
