from __future__ import annotations

import asyncio
import os
import time

from app.config import Config, load_config
from app.engine.trading_service import TradingService
from app.exchange.ccxt_adapter import CcxtAdapter
from app.exchange.paper_adapter import PaperAdapter
from app.persistence.logger import FileLogger
from app.persistence.store import JsonStore


def build_adapter(config: Config):
    mode = config.execution_mode
    if mode == "paper":
        # real Bitget public market data, virtual fills/balance, no keys
        return PaperAdapter(CcxtAdapter(), start_balance=float(os.getenv("PAPER_BALANCE", "10000")))
    return CcxtAdapter(
        api_key=os.getenv("BITGET_KEY", ""),
        secret=os.getenv("BITGET_SECRET", ""),
        password=os.getenv("BITGET_PASSPHRASE", ""),
        testnet=(mode == "testnet"),
    )


async def run(config: Config, max_cycles: int | None = None) -> None:
    logger = FileLogger(base=config.log_path, console=config.enable_console_log)
    adapter = build_adapter(config)
    stores = (JsonStore("SAVE/wallets.json"), JsonStore("SAVE/records.json"))
    service = TradingService(adapter, config, stores[0], stores[1], logger)
    service.start()
    universe_limit = int(os.getenv("UNIVERSE_LIMIT", "120"))
    sleep_s = float(os.getenv("CYCLE_SLEEP", "5"))
    cycles = 0
    try:
        while service.is_running:
            symbols = (await adapter.load_markets())[:universe_limit]
            t0 = time.time()
            views = await service.build_views(symbols)
            logger.write("DATA", f"심볼 서칭 완료: {len(symbols)}개 ({int((time.time() - t0) * 1000)}ms)")
            await service.cycle(views, now=time.strftime("%Y-%m-%d %H:%M:%S"))
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            await asyncio.sleep(sleep_s)
    finally:
        await adapter.close()


def main() -> None:
    path = os.getenv("CONFIG_PATH", "config.json")
    if not os.path.exists(path) and os.path.exists("config.example.json"):
        import shutil

        shutil.copy("config.example.json", path)
        print(f"[uprich-bot] created {path} from config.example.json")
    config = load_config(path) if os.path.exists(path) else Config()
    if config.execution_mode == "live" and not config.execution_enabled:
        print("[SAFETY] execution_mode=live but execution_enabled=false. Refusing to place live orders.")
        print("         Set execution_mode=paper to simulate, or execution_enabled=true (with .env keys) for live.")
        return
    banner = {"paper": "PAPER (no keys, virtual fills)", "testnet": "TESTNET", "live": "LIVE (real funds)"}
    print(f"[uprich-bot] {banner.get(config.execution_mode)} on Bitget USDT-M")
    if os.getenv("HEADLESS"):
        max_cycles = int(os.getenv("MAX_CYCLES")) if os.getenv("MAX_CYCLES") else None
        asyncio.run(run(config, max_cycles=max_cycles))
        return
    from app.dashboard.server import serve

    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8000"))
    print(f"[uprich-bot] dashboard + engine -> http://{host}:{port}")
    serve(config, host, port)


if __name__ == "__main__":
    main()
