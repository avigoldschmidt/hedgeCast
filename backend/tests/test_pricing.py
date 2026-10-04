from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from hedgecast import geo
from hedgecast.engine import catalog, pricing
from hedgecast.fakes import FakeMarketData

CAP = Decimal("0.97")
BOOK = {
    "no_dollars": [["0.6800", "300"], ["0.6900", "200.5"]],
    "yes_dollars": [["0.2900", "150"], ["0.2500", "10"]],
}


def test_yes_asks_come_from_no_bids_cheapest_first():
    assert pricing.yes_asks(BOOK) == [(Decimal("0.3100"), Decimal("200.5")), (Decimal("0.3200"), Decimal("300"))]


def test_implied_probability_is_mid():
    assert pricing.implied_probability(BOOK) == pytest.approx(0.30)
    assert pricing.implied_probability({}) is None


def test_walk_crosses_levels():
    filled, cost = pricing.walk(pricing.yes_asks(BOOK), 300, CAP)
    assert filled == 300
    assert cost == Decimal("200.5") * Decimal("0.31") + Decimal("99.5") * Decimal("0.32")


def test_depth_floors_fractional_contracts_and_respects_cap():
    asks = pricing.yes_asks(BOOK)
    assert pricing.depth(asks, CAP) == 500
    assert pricing.depth(asks, Decimal("0.31")) == 200


def test_exchange_fee_rounds_up_to_cent():
    assert pricing.exchange_fee_cents(100, Decimal("0.50")) == 175
    assert pricing.exchange_fee_cents(1, Decimal("0.31")) == 2


def test_price_leg_marks_short_books_at_the_cap():
    leg = pricing.price_leg(BOOK, 600, CAP)
    assert leg["depth_contracts"] == 500
    expected = Decimal("200.5") * Decimal("0.31") + Decimal("300") * Decimal("0.32") + Decimal("99.5") * CAP
    assert leg["cost_cents"] == pricing.ceil_cents(expected)


def test_premium_rounds_up_to_whole_dollars():
    legs = [pricing.price_leg(BOOK, 100, CAP)]
    total, parts = pricing.premium(legs, "0.02", "0.10", 100)
    assert total % 100 == 0
    assert total == sum(parts.values())
    assert 0 <= parts["rounding_cents"] < 100
    assert total >= parts["hedge_cost_cents"] + parts["exchange_fee_cents"]


def test_premium_in_cents_when_bank_allows_cents():
    legs = [pricing.price_leg(BOOK, 100, CAP)]
    total, parts = pricing.premium(legs, "0.02", "0.10", 1)
    assert parts["rounding_cents"] == 0
    assert total == sum(parts.values())


def test_cost_ceiling_includes_buffer():
    leg = pricing.price_leg(BOOK, 100, CAP)
    assert pricing.cost_ceiling_cents(leg, "0.02") >= leg["cost_cents"] + leg["fee_cents"]


@pytest.mark.parametrize("km, risk", [(5, "low"), (30, "low"), (31, "medium"), (150, "medium"), (151, "high")])
def test_basis_risk_tiers(km, risk):
    assert geo.basis_risk(km) == risk


def test_nearest_station_for_ann_arbor():
    ann_arbor = geo.city("ann-arbor-mi")
    rain, rain_km = geo.nearest_station(ann_arbor, "rain")
    heat, heat_km = geo.nearest_station(ann_arbor, "heat")
    assert rain.code == "CMH"
    assert heat.high_series
    assert geo.basis_risk(rain_km) == "high"


def test_new_york_is_low_basis_risk():
    station, km = geo.nearest_station(geo.city("new-york-ny"), "rain")
    assert station.code == "NYC"
    assert geo.basis_risk(km) == "low"


def test_event_date_parses_kalshi_stamp():
    assert catalog.event_date("KXHIGHNY-26OCT04") == date(2026, 10, 4)
    assert catalog.date_stamp(date(2026, 10, 4)) == "26OCT04"


def test_triggers_pick_the_right_markets():
    data = FakeMarketData(today=date(2026, 10, 4))
    now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    nyc = geo.station("NYC")
    rain = catalog.triggers(data, "rain", nyc, now)
    assert [t["ticker"] for t in rain] == ["KXRAIN-26OCT04-NYC", "KXRAIN-26OCT05-NYC"]
    heat = catalog.triggers(data, "heat", nyc, now)
    assert all(t["ticker"].startswith("KXHIGHNY-") and t["label"] == "High of 86° or above" for t in heat)
    cold = catalog.triggers(data, "cold", nyc, now)
    assert all(t["ticker"].startswith("KXLOWTNYC-") and t["label"] == "Low of 44° or below" for t in cold)


def test_triggers_skip_markets_about_to_close():
    data = FakeMarketData(today=date(2026, 10, 4))
    late = datetime(2026, 10, 5, 4, 55, tzinfo=timezone.utc)
    rain = catalog.triggers(data, "rain", geo.station("NYC"), late)
    assert [t["date"] for t in rain] == ["2026-10-05"]
    assert late + timedelta(hours=1) > datetime(2026, 10, 5, 5, tzinfo=timezone.utc)
