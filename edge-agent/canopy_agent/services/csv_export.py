import csv
import io
from collections.abc import Iterable


def rows_to_csv(rows: Iterable[dict]) -> str:
    """Turns a list of flat dicts into a CSV string — for inspection-ready exports
    (audit trail, waste log) where every row is expected to share the same columns."""
    rows = list(rows)
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
