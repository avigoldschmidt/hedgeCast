import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

load_dotenv(Path(__file__).with_name(".env"))

import bank
import db
import kalshi

db.init_db()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hedgecast-dev")
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.get("/")
def index():
    return render_template(
        "index.html",
        businesses=db.list_businesses(),
        bank_ready=bank.configured(),
        kalshi_ready=kalshi.has_credentials(),
    )


@app.post("/businesses")
def create_business_route():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    city = request.form.get("city", "").strip()
    if not name or not description or not city:
        flash("Name, what they sell, and city are required.", "error")
        return redirect(url_for("index"))
    business_id = db.create_business(name, description, city)
    flash(f"{name} is on the book.", "ok")
    return redirect(url_for("business", business_id=business_id))


@app.post("/businesses/<int:business_id>/bank-link")
def link_bank(business_id):
    record = db.get_business(business_id)
    if record is None:
        abort(404)
    if record["bank_account_id"]:
        flash("A bank account is already linked.", "ok")
        return redirect(url_for("business", business_id=business_id))
    try:
        customer_id, account_id = bank.link(record["name"], record["city"])
    except (bank.ConfigError, bank.ApiError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("business", business_id=business_id))
    db.set_business_bank(business_id, customer_id, account_id)
    flash("Checking account linked.", "ok")
    return redirect(url_for("business", business_id=business_id))


@app.get("/businesses/<int:business_id>")
def business(business_id):
    record = db.get_business(business_id)
    if record is None:
        abort(404)
    balance = None
    balance_error = None
    if record["bank_account_id"]:
        try:
            account_id, raw = bank.balance(record["bank_customer_id"], record["bank_account_id"])
            _remember_account(record, account_id)
            balance = f"{raw:.2f}"
        except (bank.ConfigError, bank.ApiError, TypeError, ValueError) as exc:
            balance_error = str(exc)
    hedges = []
    for hedge in db.list_hedges(business_id):
        hedge["payout_label"] = _payout_label(hedge)
        hedge["kalshi_result"] = None
        hedge["market_error"] = None
        if hedge["status"] in ("filled", "held"):
            try:
                market = kalshi.get_market(hedge["ticker"])
                hedge["kalshi_result"] = kalshi.settled_result(market)
                hedge["market_status"] = market.get("status") or ""
            except kalshi.ApiError as exc:
                hedge["market_error"] = str(exc)
                hedge["market_status"] = ""
        hedges.append(hedge)
    return render_template(
        "business.html",
        business=record,
        balance=balance,
        balance_error=balance_error,
        hedges=hedges,
    )


@app.get("/businesses/<int:business_id>/hedge")
def hedge_form(business_id):
    record = db.get_business(business_id)
    if record is None:
        abort(404)
    if not record["bank_account_id"]:
        flash("Link a bank account before buying a hedge.", "error")
        return redirect(url_for("business", business_id=business_id))
    ticker = request.args.get("ticker", "").strip()
    lookup = None
    lookup_error = None
    if ticker:
        try:
            lookup = kalshi.summarize_market(kalshi.get_market(ticker))
        except kalshi.ApiError as exc:
            lookup_error = str(exc)
    markets = []
    markets_error = None
    try:
        markets = kalshi.list_open_markets()
    except kalshi.ApiError as exc:
        markets_error = str(exc)
    balance = None
    balance_error = None
    try:
        balance = kalshi.portfolio_balance()
    except (kalshi.ConfigError, kalshi.ApiError) as exc:
        balance_error = str(exc)
    return render_template(
        "hedge.html",
        business=record,
        markets=markets,
        markets_error=markets_error,
        lookup=lookup,
        lookup_error=lookup_error,
        ticker=ticker,
        kalshi_ready=kalshi.has_credentials(),
        balance=balance,
        balance_error=balance_error,
    )


@app.post("/businesses/<int:business_id>/hedge")
def hedge_buy(business_id):
    record = db.get_business(business_id)
    if record is None:
        abort(404)
    if not record["bank_account_id"]:
        flash("Link a bank account before buying a hedge.", "error")
        return redirect(url_for("business", business_id=business_id))
    ticker = request.form.get("ticker", "").strip()
    if not ticker:
        flash("Choose a market.", "error")
        return redirect(url_for("hedge_form", business_id=business_id))
    try:
        count = _contract_count(request.form.get("count", ""))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("hedge_form", business_id=business_id, ticker=ticker))
    try:
        market = kalshi.get_market(ticker)
        summary = kalshi.summarize_market(market)
    except kalshi.ApiError as exc:
        flash(str(exc), "error")
        return redirect(url_for("hedge_form", business_id=business_id, ticker=ticker))
    if not summary["crosses"]:
        flash("There is no YES ask to buy.", "error")
        return redirect(url_for("hedge_form", business_id=business_id, ticker=ticker))
    try:
        order = kalshi.buy_yes(ticker, count, summary["order_price"])
    except kalshi.ConfigError as exc:
        flash(str(exc), "error")
        return redirect(url_for("hedge_form", business_id=business_id, ticker=ticker))
    except kalshi.ApiError as exc:
        db.create_hedge(
            business_id,
            ticker,
            summary["title"],
            f"{count}.00",
            summary["order_price"],
            "",
            "",
            "0.00",
            "rejected",
            str(exc),
        )
        flash(str(exc), "error")
        return redirect(url_for("business", business_id=business_id))
    status, detail = kalshi.classify_fill(order["fill_count"], order["remaining_count"], f"{count}.00")
    moved = None
    if status == "filled":
        premium = (_decimal(order["fill_count"]) or Decimal("0")) * (_decimal(summary["order_price"]) or Decimal("0"))
        premium = premium.quantize(Decimal("0.01"))
        try:
            account_id, _transfer_id, moved = bank.charge(
                record["bank_customer_id"],
                record["bank_account_id"],
                premium,
                f"HedgeCast premium {ticker}",
            )
            _remember_account(record, account_id)
        except (bank.ConfigError, bank.ApiError) as exc:
            db.create_hedge(
                business_id,
                ticker,
                summary["title"],
                f"{count}.00",
                summary["order_price"],
                order["client_order_id"],
                order["order_id"],
                order["fill_count"],
                "rejected",
                f"Kalshi filled {order['fill_count']} contracts, but checking was not charged. {exc}",
            )
            flash(str(exc), "error")
            return redirect(url_for("business", business_id=business_id))
    db.create_hedge(
        business_id,
        ticker,
        summary["title"],
        f"{count}.00",
        summary["order_price"],
        order["client_order_id"],
        order["order_id"],
        order["fill_count"],
        status,
        detail,
    )
    if status == "filled":
        flash(
            f"Bought YES on {ticker}. {order['fill_count']} contracts filled. ${moved:.2f} came out of checking.",
            "ok",
        )
    else:
        flash(f"Order resting on {ticker}. Nothing has filled yet.", "ok")
    return redirect(url_for("business", business_id=business_id))


@app.get("/api/markets/<ticker>")
def market_quote(ticker):
    try:
        summary = kalshi.summarize_market(kalshi.get_market(ticker))
    except kalshi.ApiError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(summary)


@app.post("/hedges/<int:hedge_id>/resolve")
def resolve_hedge(hedge_id):
    hedge = db.get_hedge(hedge_id)
    if hedge is None:
        abort(404)
    record = db.get_business(hedge["business_id"])
    back = url_for("business", business_id=hedge["business_id"])
    if hedge["status"] in ("paid", "lost"):
        flash("This hedge is already settled.", "error")
        return redirect(back)
    if hedge["status"] != "filled":
        flash("This hedge cannot be settled.", "error")
        return redirect(back)
    filled = _decimal(hedge["fill_count"]) or Decimal("0")
    if filled <= 0:
        flash("An unfilled order cannot be paid.", "error")
        return redirect(back)
    try:
        market = kalshi.get_market(hedge["ticker"])
    except kalshi.ApiError as exc:
        flash(str(exc), "error")
        return redirect(back)
    result = kalshi.settled_result(market)
    if result is None:
        flash("This market is still open.", "error")
        return redirect(back)
    if result == "no":
        db.settle_hedge(
            hedge_id,
            "lost",
            "no",
            "kalshi",
            "Settled by Kalshi. The hedge lost. No payout was sent, and the premium stays in the reserve.",
        )
        flash("The hedge lost. No payout was sent.", "ok")
        return redirect(back)
    amount = filled.quantize(Decimal("0.01"))
    try:
        account_id, transfer_id, moved = bank.payout(
            record["bank_customer_id"],
            record["bank_account_id"],
            amount,
            f"HedgeCast payout {hedge['ticker']}",
        )
        _remember_account(record, account_id)
    except (bank.ConfigError, bank.ApiError) as exc:
        flash(str(exc), "error")
        return redirect(back)
    db.settle_hedge(
        hedge_id,
        "paid",
        "yes",
        "kalshi",
        f"Settled by Kalshi. Paid ${moved:.2f} into the checking account.",
        transfer_id,
    )
    flash(f"Paid ${moved:.2f} into the checking account.", "ok")
    return redirect(back)


@app.errorhandler(404)
def not_found(_exc):
    return render_template("error.html", message="That page is not in the book."), 404


def _remember_account(record, account_id):
    if account_id and account_id != record["bank_account_id"]:
        db.set_business_account(record["id"], account_id)
        record["bank_account_id"] = account_id


def _contract_count(raw):
    try:
        count = int(raw)
    except (TypeError, ValueError):
        raise ValueError("Contract count has to be a whole number.") from None
    if count < 1 or count > 50:
        raise ValueError("Buy between 1 and 50 contracts.")
    return count


def _decimal(raw):
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return None


def _payout_label(hedge):
    filled = _decimal(hedge.get("fill_count")) or Decimal("0")
    if hedge["status"] == "paid":
        return f"${filled.quantize(Decimal('0.01')):.2f}"
    if hedge["status"] == "lost":
        return "$0.00"
    if hedge["status"] in ("filled", "held") and filled > 0:
        return f"${filled.quantize(Decimal('0.01')):.2f} if YES"
    return "—"
