from __future__ import annotations

import time

import aiohttp
import ccxt.async_support as ccxt

from .base import ExchangeAdapter, Fill, Ticker


class CcxtAdapter(ExchangeAdapter):
    """Bitget USDT-M (mix) futures via ccxt. Live/testnet.

    - Exposes the exchange raw id ('BTCUSDT') as the canonical symbol and maps to
      ccxt unified ('BTC/USDT:USDT') internally, so the rest of the bot, the
      dashboard and config all use 'BTCUSDT' like the original.
    - Forces aiohttp's ThreadedResolver (system getaddrinfo): aiodns/c-ares fails
      on some Windows setups with 'Could not contact DNS servers' even when DNS
      and the internet are fine.
    """

    def __init__(self, api_key: str = "", secret: str = "", password: str = "", testnet: bool = False):
        self._x = ccxt.bitget({
            "apiKey": api_key,
            "secret": secret,
            "password": password,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
        if testnet:
            self._x.set_sandbox_mode(True)
        self._to_unified: dict[str, str] = {}  # id  -> unified
        self._to_id: dict[str, str] = {}       # unified -> id
        self._ohlcv_cache: dict[tuple[str, str], tuple[float, list]] = {}

    async def _ensure(self) -> None:
        if self._x.session is None:
            self._x.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver()),
                trust_env=True,
            )

    def _u(self, symbol: str) -> str:
        return self._to_unified.get(symbol, symbol)

    def amount_to_precision(self, symbol: str, qty: float) -> float:
        try:
            return float(self._x.amount_to_precision(self._u(symbol), qty))
        except Exception:
            return qty

    async def load_markets(self) -> list[str]:
        await self._ensure()
        markets = await self._x.load_markets()
        self._to_unified.clear()
        self._to_id.clear()
        for unified, m in markets.items():
            if m.get("swap") and m.get("quote") == "USDT" and m.get("settle") == "USDT":
                self._to_unified[m["id"]] = unified
                self._to_id[unified] = m["id"]
        return list(self._to_unified.keys())

    def _map_ticker(self, symbol: str, t: dict) -> Ticker:
        info = t.get("info") or {}

        def g(*keys: str) -> float:
            for k in keys:
                v = t.get(k) if k in t else info.get(k)
                if v not in (None, ""):
                    return float(v)
            return 0.0

        return Ticker(
            symbol=symbol,
            last=g("last", "lastPr"),
            open_utc=g("open", "openUtc"),
            mark=g("markPrice"),
            index=g("indexPrice"),
            funding_rate=g("fundingRate"),
            bid=g("bid", "bidPr"),
            ask=g("ask", "askPr"),
            quote_volume=g("quoteVolume", "usdtVolume"),
            high=g("high", "high24h"),
            low=g("low", "low24h"),
        )

    async def fetch_ticker(self, symbol: str) -> Ticker:
        await self._ensure()
        return self._map_ticker(symbol, await self._x.fetch_ticker(self._u(symbol)))

    async def fetch_tickers(self) -> list[Ticker]:
        await self._ensure()
        tickers = await self._x.fetch_tickers()
        out: list[Ticker] = []
        for unified, t in tickers.items():
            mid = self._to_id.get(unified)
            if mid:
                out.append(self._map_ticker(mid, t))
        return out

    _OHLCV_TTL = {"1m": 0, "15m": 0, "1h": 0, "4h": 300.0, "1d": 1800.0}  # higher TFs change slowly -> cache

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[list[float]]:
        await self._ensure()
        ttl = self._OHLCV_TTL.get(timeframe, 0.0)
        key = (symbol, timeframe)
        if ttl:
            hit = self._ohlcv_cache.get(key)
            if hit and (time.monotonic() - hit[0]) < ttl:
                return hit[1]
        data = await self._x.fetch_ohlcv(self._u(symbol), timeframe, limit=limit)
        if ttl:
            self._ohlcv_cache[key] = (time.monotonic(), data)
        return data

    async def fetch_balance(self) -> float:
        await self._ensure()
        bal = await self._x.fetch_balance()
        return float((bal.get("USDT") or {}).get("free") or 0.0)

    async def set_leverage(self, symbol: str, leverage: int, side: str) -> None:
        await self._ensure()
        await self._x.set_leverage(leverage, self._u(symbol))

    async def create_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Fill:
        await self._ensure()
        qty = self.amount_to_precision(symbol, qty)
        order_side = "buy" if side == "long" else "sell"
        if reduce_only:
            order_side = "buy" if side == "short" else "sell"
        order = await self._x.create_order(self._u(symbol), "market", order_side, qty, None, {"reduceOnly": reduce_only})
        price = float(order.get("average") or order.get("price") or 0.0)
        return Fill(symbol=symbol, side=side, price=price, qty=qty)

    async def close(self) -> None:
        await self._x.close()
