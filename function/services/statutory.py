"""
Malaysian statutory contribution tables: SOCSO (Act 4) and EIS (Act 800).

Both schemes work the same way. Wages fall into RM100 bands, and the
contribution is a percentage of the *band midpoint* rounded to the nearest five
sen -- not a percentage of the actual wage. RM1,999 and RM1,901 therefore
contribute identically, and computing straight off the wage gives an answer
that is close but wrong.

Rates, both for Category 1 (Employment Injury + Invalidity):

    SOCSO   employer 1.75%   employee 0.50%   wages capped at RM6,000
    EIS     employer 0.20%   employee 0.20%   wages capped at RM5,000

The caps are on the wage, so every band above the cap pays the cap's amount.

Verified against the PERKESO Borang 8A receipts in the payroll records: the
EIS totals computed here reproduce all 32 filed figures exactly.

A note on which wage to use. The Act counts overtime as wages, so the
contribution should be assessed on gross pay. The figures actually filed for
these employees were assessed on basic pay alone, which is why callers pass the
wage explicitly rather than having it inferred here -- reproducing a historical
filing and computing what a filing should be are different questions, and this
module should not quietly answer one when asked the other.
"""
from decimal import Decimal, ROUND_HALF_UP

ZERO = Decimal("0.00")
FIVE_SEN = Decimal("0.05")

SOCSO_WAGE_CAP = Decimal("6000")
SOCSO_EMPLOYER_RATE = Decimal("0.0175")
SOCSO_EMPLOYEE_RATE = Decimal("0.005")

EIS_WAGE_CAP = Decimal("5000")
EIS_EMPLOYER_RATE = Decimal("0.002")
EIS_EMPLOYEE_RATE = Decimal("0.002")

# Below this, PERKESO charges nothing at all rather than a token amount.
MIN_WAGE = Decimal("30")


def _round_5sen(amount):
    """PERKESO's tables are published to the nearest five sen."""
    return (amount / FIVE_SEN).quantize(Decimal("1"), ROUND_HALF_UP) * FIVE_SEN


def band_midpoint(wage, cap):
    """
    The RM100 band a wage falls in, as its midpoint, capped.

    Bands are (n, n+100] -- RM2,000.00 sits in 1,900.01-2,000.00, not in the
    band above it, which is the one boundary case worth getting right because
    round salaries land on it constantly.
    """
    w = Decimal(str(wage))
    if w <= 0:
        return ZERO
    w = min(w, Decimal(str(cap)))
    upper = ((w - Decimal("0.01")) // 100 + 1) * 100
    return (upper - 100 + upper) / 2


def socso(wage):
    """Category 1 SOCSO for one month's wage. Returns (employer, employee)."""
    w = Decimal(str(wage or 0))
    if w < MIN_WAGE:
        return ZERO, ZERO
    mid = band_midpoint(w, SOCSO_WAGE_CAP)
    return (_round_5sen(mid * SOCSO_EMPLOYER_RATE),
            _round_5sen(mid * SOCSO_EMPLOYEE_RATE))


def eis(wage):
    """EIS for one month's wage. Returns (employer, employee)."""
    w = Decimal(str(wage or 0))
    if w < MIN_WAGE:
        return ZERO, ZERO
    mid = band_midpoint(w, EIS_WAGE_CAP)
    return (_round_5sen(mid * EIS_EMPLOYER_RATE),
            _round_5sen(mid * EIS_EMPLOYEE_RATE))
