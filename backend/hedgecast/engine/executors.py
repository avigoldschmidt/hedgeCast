"""Hedge execution. Paper fills against the live book by default because the Kalshi demo account can't be funded."""

import uuid
from decimal import Decimal

from ..integrations import kalshi
from .pricing import asks, ceil_cents, exchange_fee_cents, walk


class HedgeError(Exception):
    def __init__(self, message, orphaned=()):
        super().__init__(message)
        self.orphaned = list(orphaned)


def _plan(book, leg, max_price):
    offers = asks(book, leg["side"])
    filled, cost = walk(offers, leg["contracts"], max_price)
    if filled < leg["contracts"]:
        raise HedgeError(f"Only {int(filled)} of {leg['contracts']} contracts were on offer for {leg['ticker']}.")
    avg = cost / Decimal(leg["contracts"])
    fee = exchange_fee_cents(leg["contracts"], avg)
    total = ceil_cents(cost) + fee
    if total > leg["cost_ceiling_cents"]:
        raise HedgeError(f"The price for {leg['ticker']} moved past the quote.")
    limit = max(price for price, _size in offers if price <= max_price)
    return avg, total, fee, limit


def _ticket(ticker, fill_price, limit_price, fee_cents, cost_cents, order_id):
    return {
        "ticker": ticker,
        "fill_price": fill_price,
        "limit_price": limit_price,
        "fee_cents": fee_cents,
        "cost_cents": cost_cents,
        "order_id": order_id,
    }


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
            avg, total, fee, limit = _plan(self.market_data.orderbook(leg["ticker"]), leg, self.max_price)
            fills.append(
                _ticket(
                    leg["ticker"],
                    f"{avg:.4f}",
                    f"{limit:.4f}",
                    fee,
                    total,
                    f"paper-{uuid.uuid4().hex[:12]}",
                )
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
            _avg, _total, _fee, limit = _plan(self.market_data.orderbook(leg["ticker"]), leg, self.max_price)
            try:
                order = kalshi.buy(leg["ticker"], leg["side"], leg["contracts"], f"{limit:.4f}")
            except (kalshi.ConfigError, kalshi.ApiError) as exc:
                raise HedgeError(str(exc), orphaned=fills) from exc
            filled = Decimal(order["fill_count"] or "0")
            if filled < leg["contracts"]:
                raise HedgeError(
                    f"Kalshi filled {filled} of {leg['contracts']} contracts for {leg['ticker']}.",
                    orphaned=fills + [{"ticker": leg["ticker"], "order_id": order["order_id"]}],
                )
            fee = exchange_fee_cents(leg["contracts"], limit)
            fills.append(
                _ticket(
                    leg["ticker"],
                    f"{limit:.4f}",
                    f"{limit:.4f}",
                    fee,
                    ceil_cents(filled * limit) + fee,
                    order["order_id"],
                )
            )
        return fills


def make_executor(mode, market_data, max_price):
    if mode == "live":
        return LiveExecutor(market_data, max_price)
    return PaperExecutor(market_data, max_price)
