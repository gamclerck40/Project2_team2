import os

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# =========================
# ✅ PDF 유틸
# =========================


# 영수증 PDF 페이지 폰트 적용.
def _register_korean_font():
    """
    static/fonts/NanumGothic.ttf 가 있으면 등록 -> 한글 PDF 가능
    없으면 Helvetica로 fallback
    """
    font_path = os.path.join(
        settings.BASE_DIR, "static", "fonts", "NanumGothic-Regular.ttf"
    )
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("NanumGothic-Regular", font_path))
            return "NanumGothic-Regular"
        except Exception:
            return "Helvetica"
    return "Helvetica"


# Transaction.amount가 Decimal형일 수 있으니, 'f"{ammount:,}원"같은 포맷팅 할 함수.
def _money_int(v):
    try:
        return int(v)
    except Exception:
        return 0


"""
부가세 10% 가정:
총액 = 공급가 + 부가세
공급가 = 총액 / 1.1
부가세 = 총액 - 공급가
"""


def _calc_vat(amount_won: int):

    if amount_won <= 0:
        return 0, 0, 0
    supply = int(round(amount_won / 1.1))
    vat = amount_won - supply
    fee = 0
    return supply, vat, fee
