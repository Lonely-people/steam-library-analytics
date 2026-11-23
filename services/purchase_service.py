"""Purchase-record service: CRUD plus cost semantics.

Cost rules from PLAN.md §4.3 / §7:

* A refunded record never counts toward net spend, but the row is kept so
  the purchase history stays auditable.
* Zero cost and "cost unknown" are different things. Unknown cost is
  expressed by the library entry's ``purchase_records_complete = FALSE``,
  never by an empty purchase list.
* Only records dated on a calendar day are accepted; openGauss stores DATE
  as timestamp(0) and the schema CHECK enforces the same rule.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from database.db import get_connection

PURCHASE_TYPES = ("base", "dlc")
PURCHASE_STATUSES = ("paid", "refunded")


class PurchaseError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PurchaseValidationError(PurchaseError):
    pass


class PurchaseNotFoundError(PurchaseError):
    pass


@dataclass(frozen=True)
class Purchase:
    purchase_id: int
    library_id: int
    game_id: int
    game_name: str
    purchase_date: dt.date | None
    paid_amount: Decimal
    purchase_type: str
    status: str
    notes: str | None

    @property
    def effective_amount(self) -> Decimal:
        """Amount that counts toward net spend (refunds are zero)."""
        return self.paid_amount if self.status == "paid" else Decimal("0.00")


@dataclass(frozen=True)
class CostSummary:
    library_id: int
    game_name: str
    records_complete: bool
    record_count: int
    net_paid: Decimal
    refunded_total: Decimal
    play_minutes: int
    acquisition_type: str

    def __post_init__(self) -> None:
        # SUM() over zero rows returns 0 (scale 0), not 0.00. Normalise once
        # here so every consumer sees the same 2-decimal money format.
        object.__setattr__(self, "net_paid", self.net_paid.quantize(Decimal("0.01")))
        object.__setattr__(
            self, "refunded_total", self.refunded_total.quantize(Decimal("0.01"))
        )

    @property
    def cost_state(self) -> str:
        """One of: unknown, free, paid, none."""
        if not self.records_complete:
            return "unknown"
        if self.record_count == 0:
            return "free" if self.acquisition_type in (
                "free_to_play", "free_claimed", "gift") else "none"
        return "paid" if self.net_paid > 0 else "free"

    @property
    def cost_per_hour(self) -> Decimal | None:
        """Net paid cost per hour; undefined when free or unplayed."""
        if self.net_paid <= 0 or self.play_minutes <= 0:
            return None
        return (self.net_paid * 60 / self.play_minutes).quantize(Decimal("0.01"))


_PURCHASE_SELECT = """
SELECT p.purchase_id, p.library_id, e.game_id, g.game_name, p.purchase_date,
       p.paid_amount, p.purchase_type, p.status, p.notes
FROM steam.purchases p
JOIN steam.library_entries e ON e.library_id = p.library_id
JOIN steam.games g ON g.game_id = e.game_id
"""


def _row_to_purchase(row) -> Purchase:
    return Purchase(
        purchase_id=row[0],
        library_id=row[1],
        game_id=row[2],
        game_name=row[3],
        purchase_date=row[4].date() if isinstance(row[4], dt.datetime) else row[4],
        paid_amount=Decimal(row[5]),
        purchase_type=row[6],
        status=row[7],
        notes=row[8],
    )


def _parse_date(value: Any) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError as exc:
            raise PurchaseValidationError("purchase_date must be YYYY-MM-DD") from exc
    raise PurchaseValidationError("purchase_date must be a date string or null")


def _parse_amount(value: Any) -> Decimal:
    if value is None or value == "":
        raise PurchaseValidationError("paid_amount is required")
    if isinstance(value, bool):
        raise PurchaseValidationError("paid_amount must be a number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PurchaseValidationError("paid_amount must be a number") from exc
    if amount < 0:
        raise PurchaseValidationError("paid_amount cannot be negative")
    if amount != amount.quantize(Decimal("0.01")):
        raise PurchaseValidationError("paid_amount allows at most 2 decimals")
    if amount >= Decimal(100000000):
        raise PurchaseValidationError("paid_amount is too large")
    return amount


def _clean_notes(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PurchaseValidationError("notes must be a string")
    value = value.strip()
    return value or None


def _ensure_library_entry(cur, game_id: int) -> int:
    cur.execute(
        "SELECT library_id FROM steam.library_entries WHERE game_id = %s", (game_id,)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO steam.library_entries (game_id) VALUES (%s) RETURNING library_id",
        (game_id,),
    )
    return cur.fetchone()[0]


def list_purchases(*, game_id: int | None = None) -> list[Purchase]:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            if game_id is None:
                cur.execute(f"{_PURCHASE_SELECT} ORDER BY p.purchase_date DESC NULLS LAST, p.purchase_id DESC")
            else:
                cur.execute(
                    f"{_PURCHASE_SELECT} WHERE e.game_id = %s "
                    "ORDER BY p.purchase_date DESC NULLS LAST, p.purchase_id DESC",
                    (game_id,),
                )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_purchase(r) for r in rows]


def get_purchase(purchase_id: int) -> Purchase:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"{_PURCHASE_SELECT} WHERE p.purchase_id = %s", (purchase_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise PurchaseNotFoundError("purchase not found")
    return _row_to_purchase(row)


def _clean_type(value: Any) -> str:
    value = value or "base"
    if value not in PURCHASE_TYPES:
        raise PurchaseValidationError("purchase_type must be base or dlc")
    return value


def _clean_status(value: Any) -> str:
    value = value or "paid"
    if value not in PURCHASE_STATUSES:
        raise PurchaseValidationError("status must be paid or refunded")
    return value


def create_purchase(data: dict[str, Any]) -> Purchase:
    game_id = data.get("game_id")
    if not isinstance(game_id, int) or isinstance(game_id, bool):
        raise PurchaseValidationError("game_id is required")

    purchase_date = _parse_date(data.get("purchase_date"))
    amount = _parse_amount(data.get("paid_amount"))
    purchase_type = _clean_type(data.get("purchase_type"))
    status = _clean_status(data.get("status"))
    notes = _clean_notes(data.get("notes"))

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM steam.games WHERE game_id = %s", (game_id,))
            if cur.fetchone() is None:
                raise PurchaseValidationError("game_id does not exist")
            library_id = _ensure_library_entry(cur, game_id)
            cur.execute(
                "INSERT INTO steam.purchases (library_id, purchase_date, paid_amount, "
                "purchase_type, status, notes) VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING purchase_id",
                (library_id, purchase_date, amount, purchase_type, status, notes),
            )
            purchase_id = cur.fetchone()[0]
    finally:
        conn.close()
    return get_purchase(purchase_id)


def update_purchase(purchase_id: int, data: dict[str, Any]) -> Purchase:
    current = get_purchase(purchase_id)

    purchase_date = (
        _parse_date(data.get("purchase_date"))
        if "purchase_date" in data else current.purchase_date
    )
    amount = (
        _parse_amount(data.get("paid_amount"))
        if "paid_amount" in data else current.paid_amount
    )
    purchase_type = (
        _clean_type(data.get("purchase_type"))
        if "purchase_type" in data else current.purchase_type
    )
    status = _clean_status(data.get("status")) if "status" in data else current.status
    notes = _clean_notes(data.get("notes")) if "notes" in data else current.notes

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE steam.purchases SET purchase_date = %s, paid_amount = %s, "
                "purchase_type = %s, status = %s, notes = %s, updated_at = now() "
                "WHERE purchase_id = %s",
                (purchase_date, amount, purchase_type, status, notes, purchase_id),
            )
    finally:
        conn.close()
    return get_purchase(purchase_id)


def delete_purchase(purchase_id: int) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM steam.purchases WHERE purchase_id = %s", (purchase_id,))
            if cur.rowcount == 0:
                raise PurchaseNotFoundError("purchase not found")
    finally:
        conn.close()


def cost_summary(game_id: int) -> CostSummary:
    """Aggregate a game's purchase records into a cost view.

    ``records_complete`` comes from the library entry, because only the user
    can state whether every purchase has been recorded.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT e.library_id, g.game_name, e.purchase_records_complete, "
                "COALESCE(e.play_minutes, 0), e.acquisition_type, "
                "COALESCE(SUM(CASE WHEN p.status = 'paid' THEN p.paid_amount ELSE 0 END), 0), "
                "COALESCE(SUM(CASE WHEN p.status = 'refunded' THEN p.paid_amount ELSE 0 END), 0), "
                "COUNT(p.purchase_id) "
                "FROM steam.library_entries e "
                "JOIN steam.games g ON g.game_id = e.game_id "
                "LEFT JOIN steam.purchases p ON p.library_id = e.library_id "
                "WHERE e.game_id = %s "
                "GROUP BY e.library_id, g.game_name, e.purchase_records_complete, "
                "e.play_minutes, e.acquisition_type",
                (game_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise PurchaseNotFoundError("game has no library entry")

    return CostSummary(
        library_id=row[0],
        game_name=row[1],
        records_complete=bool(row[2]),
        play_minutes=int(row[3]),
        acquisition_type=row[4],
        net_paid=Decimal(row[5]),
        refunded_total=Decimal(row[6]),
        record_count=int(row[7]),
    )
