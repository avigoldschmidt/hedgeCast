"""Pure pricing math. Money is integer cents; contract prices are Decimal dollars."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

ONE = Decimal("1")
CENT = Decimal("0.01")


def ceil_cents(dollars):
    return int((Decimal(dollars) * 100).to_integral_value(rounding=ROUND_CEILING))


def round_up(cents, unit):
    return -(-cents // unit) * unit


def yes_asks(orderbook):
    """YES asks, cheapest first. Kalshi books list bids only, so a NO bid at p is a YES ask at 1 - p."""
    asks = []
    for price, size in orderbook.get("no_dollars") or []:
        ask = ONE - Decimal(str(price))
        quantity = Decimal(str(size))
        if ask > 0 and quantity > 0:
            asks.append((ask, quantity))
    asks.sort(key=lambda level: level[0])
    return asks


def best_bid(orderbook):
    bids = [Decimal(str(price)) for price, size in orderbook.get("yes_dollars") or [] if Decimal(str(size)) > 0]
    return max(bids) if bids else None


def implied_probability(orderbook):
    asks = yes_asks(orderbook)
    bid = best_bid(orderbook)
    if asks and bid is not None:
        return float((asks[0][0] + bid) / 2)
    if asks:
        return float(asks[0][0])
    if bid is not None:
        return float(bid)
    return None


def depth(asks, max_price):
    total = sum((size for price, size in asks if price <= max_price), Decimal("0"))
    return int(total.to_integral_value(rounding=ROUND_FLOOR))


def walk(asks, contracts, max_price):
    """Buys up to `contracts` from the cheapest asks at or under max_price. Returns (filled, cost) as Decimals."""
    remaining = Decimal(contracts)
    cost = Decimal("0")
    for price, size in asks:
        if price > max_price or remaining <= 0:
            break
        take = min(size, remaining)
        cost += take * price
        remaining -= take
    return Decimal(contracts) - remaining, cost


def exchange_fee_cents(contracts, price):
    """Kalshi taker fee: 7% x C x P x (1 - P), rounded up to the cent."""
    price = Decimal(price)
    return ceil_cents(Decimal("0.07") * Decimal(contracts) * price * (ONE - price))


def price_leg(orderbook, contracts, max_price):
    """Prices `contracts` YES contracts. Anything the book can't cover is priced at max_price."""
    asks = yes_asks(orderbook)
    available = depth(asks, max_price)
    filled, cost = walk(asks, contracts, max_price)
    cost += (Decimal(contracts) - filled) * max_price
    avg = (cost / Decimal(contracts)) if contracts else Decimal("0")
    return {
        "contracts": contracts,
        "avg_price": avg.quantize(Decimal("0.0001")),
        "cost_cents": ceil_cents(cost),
        "fee_cents": exchange_fee_cents(contracts, avg),
        "depth_contracts": available,
        "implied_probability": implied_probability(orderbook),
    }


def premium(legs, buffer_rate, platform_rate, unit_cents):
    """Premium in cents, rounded up to the bank's smallest unit, plus its breakdown."""
    hedge = sum(leg["cost_cents"] for leg in legs)
    fees = sum(leg["fee_cents"] for leg in legs)
    base = Decimal(hedge + fees)
    buffer = ceil_cents(base * Decimal(buffer_rate) / 100)
    platform = ceil_cents(base * Decimal(platform_rate) / 100)
    raw = hedge + fees + buffer + platform
    total = round_up(raw, unit_cents)
    return total, {
        "hedge_cost_cents": hedge,
        "exchange_fee_cents": fees,
        "buffer_cents": buffer,
        "platform_fee_cents": platform,
        "rounding_cents": total - raw,
    }


def cost_ceiling_cents(leg, buffer_rate):
    """The most the hedge for a leg may cost at execution before we refuse it."""
    base = Decimal(leg["cost_cents"] + leg["fee_cents"])
    return ceil_cents(base * (ONE + Decimal(buffer_rate)) / 100)
