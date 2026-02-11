import os

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def register_korean_font() -> str:
    """
    static/fonts/NanumGothic-Regular.ttf 가 있으면 등록 -> 한글 PDF 가능
    없으면 Helvetica로 fallback
    """
    font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "NanumGothic-Regular.ttf")
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("NanumGothic-Regular", font_path))
            return "NanumGothic-Regular"
        except Exception:
            return "Helvetica"
    return "Helvetica"


def money_int(v) -> int:
    """Decimal 등 숫자 타입을 int로 안전 변환"""
    try:
        return int(v)
    except Exception:
        return 0


def calc_vat(amount_won: int) -> tuple[int, int, int]:
    """
    부가세 10% 가정:
    총액 = 공급가 + 부가세
    공급가 = 총액 / 1.1
    부가세 = 총액 - 공급가
    """
    if amount_won <= 0:
        return 0, 0, 0
    supply = int(round(amount_won / 1.1))
    vat = amount_won - supply
    fee = 0
    return supply, vat, fee
