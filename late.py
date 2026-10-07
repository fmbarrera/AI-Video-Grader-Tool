"""Late-submission policy.

Due 11:59 pm Sep 23, 2026 (Eastern), with a one-day grace period: anything in
by 11:59 pm Sep 24 gets full marks. Anything later is capped at 80% of the
max points (32/40), no matter how many days late.

Edit the constants below to change the policy.
"""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
GRACE_DEADLINE = datetime(2026, 9, 24, 23, 59, 59, tzinfo=TZ)
LATE_CAP_PCT = 80.0


def days_late(submitted: datetime) -> int:
    """Whole days past the grace deadline (0 = on time). Naive datetimes are treated as Eastern."""
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=TZ)
    seconds = (submitted - GRACE_DEADLINE).total_seconds()
    return max(0, math.ceil(seconds / 86400))


def apply_late_policy(points: float, max_points: float, submitted: datetime) -> float:
    """Final points: unchanged if on time, otherwise capped at LATE_CAP_PCT of max_points."""
    if days_late(submitted) == 0:
        return points
    return min(points, max_points * LATE_CAP_PCT / 100)


if __name__ == "__main__":
    for ts in ["2026-09-23 21:27", "2026-09-24 23:59", "2026-09-25 00:01", "2026-10-04 12:00"]:
        t = datetime.fromisoformat(ts)
        print(f"{ts}  days_late={days_late(t)}  40/40 -> {apply_late_policy(40, 40, t):g}  "
              f"30/40 -> {apply_late_policy(30, 40, t):g}")
