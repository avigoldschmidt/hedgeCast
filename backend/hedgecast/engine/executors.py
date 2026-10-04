"""Hedge execution. Paper fills against the live book by default because the Kalshi demo account can't be funded."""

import uuid
from decimal import Decimal

from ..integrations import kalshi
from .pricing import ceil_cents, exchange_fee_cents, walk, yes_asks


class HedgeError(Exception):
    def __init__(self, message, orphaned=()):
        super().__init__(message)
        self.orphaned = list(orphaned)


def _plan(book, leg, max_price):
    asks = yes_asks(book)
    filled, cost = walk(asks, leg["contracts"], max_price)
    if filled < leg["contracts"]:
        raise HedgeError(f"Only {int(filled)} of {leg['contracts']} contracts were on offer for {leg['ticker']}.")
    avg = cost / Decimal(leg["contracts"])
    total = ceil_cents(cost) + exchange_fee_cents(leg["contracts"], avg)
    if total > leg["cost_ceiling_cents"]:
        raise HedgeError(f"The price for {leg['ticker']} moved past the quote.")
    limit = max(price for price, _size in asks if price <= max_price)
    return avg, total, limit


class PaperExecutor:
    mode = "paper"
    simulated = True

    def __init__(self, market_data, max_price):
        self.market_data = market_data
        self.max_price = Decimal(max_price)

    def execute(self, legs):
        """All legs fill or none do. Fills are simulated at the walked price of the live book."""
        fills = []
        for leg in legs:
            avg, total, _limit = _plan(self.market_data.orderbook(leg["ticker"]), leg, self.max_price)
            fills.append(
                {
                    "ticker": leg["ticker"],
                    "fill_price": f"{avg:.4f}",
                    "cost_cents": total,
                    "order_id": f"paper-{uuid.uuid4().hex[:12]}",
                }
            )
        return fills


class LiveExecutor:
    """Sends real orders to Kalshi. Needs a funded account; a failed later leg leaves earlier legs orphaned."""

    mode = "live"
    simulated = False

    def __init__(self, market_data, max_price):
        self.market_data = market_data
        self.max_price = Decimal(max_price)

    def execute(self, legs):
        fills = []
        for leg in legs:
            _avg, _total, limit = _plan(self.market_data.orderbook(leg["ticker"]), leg, self.max_price)
            try:
                order = kalshi.buy_yes(leg["ticker"], leg["contracts"], f"{limit:.4f}")
            except (kalshi.ConfigError, kalshi.ApiError) as exc:
                raise HedgeError(str(exc), orphaned=fills) from exc
            filled = Decimal(order["fill_count"] or "0")
            if filled < leg["contracts"]:
                raise HedgeError(
                    f"Kalshi filled {filled} of {leg['contracts']} contracts for {leg['ticker']}.",
                    orphaned=fills + [{"ticker": leg["ticker"], "order_id": order["order_id"]}],
                )
            fills.append(
                {
                    "ticker": leg["ticker"],
                    "fill_price": f"{limit:.4f}",
                    "cost_cents": ceil_cents(filled * limit) + exchange_fee_cents(leg["contracts"], limit),
                    "order_id": order["order_id"],
                }
            )
        return fills


def make_executor(mode, market_data, max_price):
    if mode == "live":
        return LiveExecutor(market_data, max_price)
    return PaperExecutor(market_data, max_price)
