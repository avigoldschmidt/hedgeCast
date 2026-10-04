"""Bank port used by the engine. Amounts are integer cents; the Nessie sandbox only moves whole dollars."""

from decimal import Decimal

from . import bank, nessie


class BankError(Exception):
    pass


class NessieBank:
    unit_cents = 100
    name = "Capital One Nessie"

    def __init__(self, settings):
        nessie.use_settings(settings.get_setting, settings.set_setting)
        self.settings = settings

    def configured(self):
        return bank.configured()

    def link(self, name, city):
        return self._call(bank.link, name, city)

    def balance_cents(self, customer_id, account_id):
        account_id, dollars = self._call(bank.balance, customer_id, account_id)
        return account_id, int(Decimal(dollars) * 100)

    def charge(self, customer_id, account_id, cents, memo):
        return self._move(bank.charge, customer_id, account_id, cents, memo)

    def pay(self, customer_id, account_id, cents, memo):
        return self._move(bank.payout, customer_id, account_id, cents, memo)

    def reserve_balance_cents(self):
        reserve_id = self.settings.get_setting(nessie.RESERVE_SETTING)
        if not reserve_id:
            return None
        return int(Decimal(str(self._call(nessie.available_balance, reserve_id))) * 100)

    def _move(self, fn, customer_id, account_id, cents, memo):
        if cents % self.unit_cents:
            raise BankError("The bank only moves whole dollars.")
        account_id, transfer_id, moved = self._call(fn, customer_id, account_id, Decimal(cents) / 100, memo)
        return account_id, transfer_id, int(Decimal(moved) * 100)

    @staticmethod
    def _call(fn, *args):
        try:
            return fn(*args)
        except (bank.ConfigError, bank.ApiError, nessie.ConfigError, nessie.ApiError) as exc:
            raise BankError(str(exc)) from exc
