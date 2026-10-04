from decimal import Decimal

import pytest

from hedgecast.integrations import kalshi, nessie


@pytest.mark.parametrize(
    "amount, expected",
    [
        ("0.21", 1),
        ("0.01", 1),
        ("1.49", 1),
        ("1.50", 2),
        ("46.40", 46),
        ("100", 100),
        ("0", 0),
    ],
)
def test_whole_dollars(amount, expected):
    assert nessie.whole_dollars(Decimal(amount)) == expected


def test_order_price_uses_ask_when_present():
    assert kalshi.order_price({"yes_ask_dollars": "0.2300"}) == ("0.2300", True)


def test_order_price_falls_back_to_resting_bid():
    assert kalshi.order_price({"yes_ask_dollars": "0"}) == (kalshi.RESTING_BID, False)
    assert kalshi.order_price({}) == (kalshi.RESTING_BID, False)


def test_classify_fill():
    assert kalshi.classify_fill("0", "5", "5.00")[0] == "resting"
    assert kalshi.classify_fill("5.00", "0", "5.00") == ("filled", "")
    status, detail = kalshi.classify_fill("2.00", "3.00", "5.00")
    assert status == "filled"
    assert "Filled 2.00 of 5.00" in detail


@pytest.mark.parametrize(
    "market, expected",
    [
        ({"result": "yes"}, "yes"),
        ({"result": "NO"}, "no"),
        ({"result": ""}, None),
        ({"result": "void"}, None),
        ({}, None),
    ],
)
def test_settled_result(market, expected):
    assert kalshi.settled_result(market) == expected


def test_price_label():
    assert kalshi.price_label("0.2300") == "23¢"
    assert kalshi.price_label("", empty="No ask") == "No ask"
