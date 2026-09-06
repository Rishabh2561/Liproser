from datetime import UTC, datetime

import pytest
from liproser.budget import BudgetExceededError, reconcile, reserve
from liproser.database import AiBudgetPeriod, engine
from sqlalchemy.orm import Session


def test_reservation_reconciliation_and_hard_stop():
    with Session(engine) as db:
        first = reserve(db, "openai", 8.0, 10.0)
        with pytest.raises(BudgetExceededError):
            reserve(db, "anthropic", 3.0, 10.0)
        reconcile(db, first.id, 7.5)
        second = reserve(db, "anthropic", 2.5, 10.0)
        reconcile(db, second.id, 2.6)
        period = db.get(AiBudgetPeriod, datetime.now(UTC).strftime("%Y-%m"))
        assert period.reserved_usd == 0
        assert period.actual_usd == pytest.approx(10.1)


def test_ollama_has_zero_external_cost():
    with Session(engine) as db:
        reservation = reserve(db, "ollama", 99, 10)
        assert reservation.actual_usd == 0
        assert reservation.status == "RECONCILED"


def test_monthly_period_is_utc():
    instant = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)
    with Session(engine) as db:
        reservation = reserve(db, "openai", 1, 10, instant)
        assert reservation.period == "2027-01"
