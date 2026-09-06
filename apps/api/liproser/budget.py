from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from .database import AiBudgetPeriod, AiCostReservation


class BudgetExceededError(RuntimeError):
    pass


def current_period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def reserve(
    db: Session, provider: str, estimate_usd: float, limit_usd: float, now: datetime | None = None
) -> AiCostReservation:
    if provider not in {"openai", "anthropic"}:
        return AiCostReservation(
            id=str(uuid4()),
            period=current_period(now),
            provider=provider,
            estimated_usd=0,
            actual_usd=0,
            status="RECONCILED",
        )
    period_id = current_period(now)
    period = db.get(AiBudgetPeriod, period_id, with_for_update=True)
    if period is None:
        period = AiBudgetPeriod(period=period_id, limit_usd=limit_usd, actual_usd=0, reserved_usd=0)
        db.add(period)
        db.flush()
    available = period.limit_usd - period.actual_usd - period.reserved_usd
    if estimate_usd > available:
        raise BudgetExceededError(
            f"Estimated cost exceeds the unreserved USD {available:.4f} balance"
        )
    reservation = AiCostReservation(
        id=str(uuid4()), period=period_id, provider=provider, estimated_usd=estimate_usd
    )
    period.reserved_usd += estimate_usd
    db.add(reservation)
    db.commit()
    return reservation


def reconcile(db: Session, reservation_id: str, actual_usd: float) -> AiCostReservation:
    reservation = db.get(AiCostReservation, reservation_id, with_for_update=True)
    if reservation is None or reservation.status != "RESERVED":
        raise ValueError("Reservation is missing or already reconciled")
    period = db.get(AiBudgetPeriod, reservation.period, with_for_update=True)
    period.reserved_usd = max(period.reserved_usd - reservation.estimated_usd, 0)
    period.actual_usd += max(actual_usd, 0)
    reservation.actual_usd = max(actual_usd, 0)
    reservation.status = "RECONCILED"
    db.commit()
    return reservation
