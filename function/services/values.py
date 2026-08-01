"""
Conversions between database values and what the JSON API exposes.

The columns are typed (timestamptz, date, numeric, boolean) but the API
contract predates them and must not move: timestamps go out as ISO 8601 with
an offset, an unset date goes out as "", and money goes out as a JSON number.
Everything that serialises a row goes through here.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation


def now():
    """Current UTC time, truncated to whole seconds like the old _now_iso()."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_iso(value):
    """timestamptz -> '2026-06-05T07:39:02+00:00'. Never None in practice."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        # Postgres always hands back an aware value; a naive one can only come
        # from a database that lost the offset, so assume the UTC we wrote.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_datetime(value):
    """ISO 8601 text (or datetime) -> aware datetime. Used by the importer."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).strip())
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_date_text(value):
    """DATE -> 'YYYY-MM-DD', and NULL -> '' as the API has always rendered it."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.isoformat()


def parse_date(value):
    """'' or None -> NULL; 'YYYY-MM-DD' -> date. Anything unparseable -> NULL."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def to_money(value):
    """NUMERIC -> float, so jsonify emits a number rather than a string."""
    if value is None:
        return None
    return float(value)


def parse_money(value):
    """Round to 2dp as Decimal. '' and unparseable input mean NULL."""
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def money_or_empty(value):
    """The API renders an unset amount as "" rather than null."""
    number = to_money(value)
    return "" if number is None else number
