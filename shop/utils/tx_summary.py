from datetime import date
from typing import List, Tuple

from django.db.models import Case, DecimalField, Sum, Value, When


def parse_month_range(sum_start: str, sum_end: str) -> Tuple[date, date]:
    """
    YYYY-MM 형태의 sum_start/sum_end를 date 범위로 변환.
    end는 '다음달 1일'을 반환(occurred_at__date__lt end 용)
    """
    sy, sm = map(int, sum_start.split("-"))
    ey, em = map(int, sum_end.split("-"))

    start = date(sy, sm, 1)
    end = date(ey + 1, 1, 1) if em == 12 else date(ey, em + 1, 1)
    return start, end


def aggregate_in_out(base_qs, in_types: List[str], out_types: List[str]):
    """
    base_qs(Transaction queryset)에 대해 IN/OUT 합계 집계.
    """
    s = base_qs.aggregate(
        _in=Sum(
            Case(
                When(tx_type__in=in_types, then="amount"),
                default=Value(0),
                output_field=DecimalField(),
            )
        ),
        _out=Sum(
            Case(
                When(tx_type__in=out_types, then="amount"),
                default=Value(0),
                output_field=DecimalField(),
            )
        ),
    )
    total_in = s["_in"] or 0
    total_out = s["_out"] or 0
    return total_in, total_out

def month_start(ym: str) -> date:
    """YYYY-MM -> 해당월 1일"""
    y, m = map(int, ym.split("-"))
    return date(y, m, 1)

def next_month_start(ym: str) -> date:
    """YYYY-MM -> 다음달 1일 (occurred_at__date__lt 용)"""
    y, m = map(int, ym.split("-"))
    if m == 12:
        return date(y + 1, 1, 1)
    return date(y, m + 1, 1)