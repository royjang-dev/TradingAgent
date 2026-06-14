from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import Config, save_config
from app.dashboard import data
from app.engine.market_overview import build_market_overview
from app.engine.trading_service import TradingService

STATIC = Path(__file__).parent / "static"
_LOG_RE = re.compile(r"^\[(.*?)\]\s(.*)$")
_CATS = ["TRADE", "DATA", "ERROR", "WARN", "INFO"]


def build_adapter(config: Config):
    from app.exchange.ccxt_adapter import CcxtAdapter
    from app.exchange.paper_adapter import PaperAdapter

    if config.execution_mode == "paper":
        return PaperAdapter(CcxtAdapter(), start_balance=float(os.getenv("PAPER_BALANCE", "10000")))
    return CcxtAdapter(
        api_key=os.getenv("BITGET_KEY", ""),
        secret=os.getenv("BITGET_SECRET", ""),
        password=os.getenv("BITGET_PASSPHRASE", ""),
        testnet=(config.execution_mode == "testnet"),
    )


def read_recent_logs(base: str, category: str = "ALL", limit: int = 200) -> dict:
    root = Path(base)
    cats = [category] if category and category != "ALL" else _CATS
    today = datetime.now().strftime("%Y_%m_%d")
    out: list[dict] = []
    for cat in cats:
        f = root / cat / f"{today}.txt"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                m = _LOG_RE.match(line)
                if m:
                    out.append({"time": m.group(1), "category": cat, "message": m.group(2)})
    out.sort(key=lambda x: x["time"], reverse=True)
    return {"total": len(out), "items": out[:limit]}


def _restore_state(service: TradingService, store_wallets, store_records) -> None:
    from app.models import Record, Wallet

    for raw in store_records.load(default=[]) or []:
        try:
            service.pm.records.append(Record.from_dict(raw))
        except Exception:
            pass
    for raw in store_wallets.load(default=[]) or []:
        try:
            w = Wallet.from_dict(raw)
            service.pm.positions[(w.name, w.side.value)] = w
        except Exception:
            pass
    # re-apply realized PnL from restored records so the paper balance survives a restart
    realized = sum(r.pnl for r in service.pm.records)
    apply = getattr(service.adapter, "apply_realized_pnl", None)
    if apply is not None and realized:
        apply(realized)


def create_app(config: Config | None = None, service: TradingService | None = None,
               adapter=None, run_engine: bool = False, config_path: str | None = None) -> FastAPI:
    if service is None:
        config = config or Config()
        adapter = build_adapter(config)
        from app.persistence.logger import FileLogger
        from app.persistence.store import JsonStore

        logger = FileLogger(base=config.log_path)
        store_wallets, store_records = JsonStore("SAVE/wallets.json"), JsonStore("SAVE/records.json")
        service = TradingService(adapter, config, store_wallets, store_records, logger)
        _restore_state(service, store_wallets, store_records)
    state = {"market": None, "symbols": list(service.config.selected_symbols)}

    app = FastAPI(title="uprich-bot")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        css_v = int((STATIC / "styles.css").stat().st_mtime)
        js_v = int((STATIC / "app.js").stat().st_mtime)
        # cache-bust by file mtime so edits always reach the browser (no stale CSS/JS)
        return (
            html.replace("/static/styles.css", f"/static/styles.css?v={css_v}")
            .replace("/static/app.js", f"/static/app.js?v={js_v}")
        )

    @app.get("/api/status")
    async def status():
        balance = await adapter.fetch_balance()
        used = sum(abs(w.entry_price * w.entry_count) / max(w.leverage, 1) for w in service.pm.list())
        base = data.build_status(balance, max(balance - used, 0.0), service.pm.list(), service.pm.records)
        return base | {"running": service.is_running, "mode": service.config.execution_mode}

    @app.get("/api/positions")
    async def positions():
        return data.serialize_positions(service.pm.list())

    @app.get("/api/records")
    async def records():
        return data.serialize_records(service.pm.records)

    @app.get("/api/daily")
    async def daily():
        return data.build_daily(service.pm.records)

    @app.get("/api/market")
    async def market():
        return data.serialize_market(state["market"])

    @app.get("/api/symbols")
    async def symbols():
        return {"universe": state["symbols"], "count": len(state["symbols"])}

    @app.get("/api/config")
    async def get_config():
        return service.config.model_dump()

    @app.post("/api/config")
    async def update_config(payload: dict):
        new = Config.model_validate(payload)
        changes = service.apply_config(new)
        if config_path:
            save_config(new, config_path)
        return {"changes": changes, "config": new.model_dump()}

    @app.get("/api/logs")
    async def logs(category: str = "ALL"):
        return read_recent_logs(service.config.log_path, category)

    @app.post("/api/start")
    async def start():
        service.start()
        return {"running": True}

    @app.post("/api/stop")
    async def stop():
        service.stop()
        return {"running": False}

    if run_engine:
        @app.on_event("startup")
        async def _startup():
            service.start()
            asyncio.create_task(_engine_loop(service, adapter, state))

    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    return app


async def _engine_loop(service, adapter, state, sleep_s=2.0):
    while service.is_running:
        try:
            symbols = await adapter.load_markets()
            state["symbols"] = symbols
            tickers = await adapter.fetch_tickers()
            state["market"] = build_market_overview(tickers)
            t0 = time.time()
            views = await service.build_views(symbols, ticker_map={t.symbol: t for t in tickers})
            if service.logger:
                service.logger.write("DATA", f"심볼 서칭 완료: {len(symbols)}개 ({int((time.time() - t0) * 1000)}ms)")
            await service.cycle(views, now=time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as exc:
            if service.logger:
                service.logger.write("ERROR", f"engine loop: {exc}")
        await asyncio.sleep(sleep_s)


def serve(config: Config | None = None, host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    config = config or Config()
    app = create_app(config=config, run_engine=True, config_path=os.getenv("CONFIG_PATH", "config.json"))
    uvicorn.run(app, host=host, port=port)
