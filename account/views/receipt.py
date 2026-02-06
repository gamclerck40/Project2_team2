from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from shop.models import Transaction
from account.models import Address
from account.utils.receipt import _calc_vat, _money_int, _register_korean_font

# ✅ 다계좌: 기본계좌 우선
from account.utils.common import get_default_account


@method_decorator(never_cache, name="dispatch")
class ReceiptPDFView(LoginRequiredMixin, View):
    """
    /accounts/receipts/<tx_id>.pdf
    Transaction 1건을 영수증 PDF로 생성

    ✅ 변경점:
    - 영수증에 "주소(기본 배송지)" 출력 추가
    - 영수증에 "계좌번호(마스킹)" 출력 개선 (****1234 형태)
    - 기존 PDF 생성 흐름/표시 로직은 그대로 유지
    """
    login_url = "login"

    def get(self, request, tx_id):
        tx = Transaction.objects.filter(id=tx_id, user=request.user).first()
        if not tx:
            raise Http404("영수증을 찾을 수 없습니다.")

        # ✅ 기본계좌(다계좌 지원)
        account = get_default_account(request.user)
        if not account:
            raise Http404("계좌 정보가 없습니다.")

        # ✅ 기본배송지(프로필에서 기본 배송지 선택 기능이 있으니 is_default가 있다고 가정)
        #    - 기본 배송지가 없으면 첫 번째 주소라도 잡거나, 없으면 "-" 처리
        default_addr = Address.objects.filter(user=request.user, is_default=True).first()
        if not default_addr:
            default_addr = Address.objects.filter(user=request.user).first()

        page_w = 80 * mm
        page_h = 110 * mm
        pagesize = portrait((page_w, page_h))

        font_name = _register_korean_font()

        filename = f"receipt_{tx.id}.pdf"
        resp = HttpResponse(content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{filename}"'

        canv = canvas.Canvas(resp, pagesize=pagesize)
        canv.setTitle(filename)

        x = 6 * mm
        y = page_h - 10 * mm

        def line():
            nonlocal y
            canv.line(x, y, page_w - x, y)
            y -= 8

        def kv(label, value, size=8):
            nonlocal y
            canv.setFont(font_name, size)
            canv.drawString(x, y, str(label))
            canv.drawRightString(page_w - x, y, str(value))
            y -= size + 5

        def kv_multiline(label, value, size=7, max_chars=24):
            """
            주소처럼 긴 텍스트를 여러 줄로 출력 (오른쪽 정렬 유지)
            """
            nonlocal y
            canv.setFont(font_name, size)
            canv.drawString(x, y, str(label))

            text = str(value) if value is not None else "-"
            if not text:
                text = "-"

            lines = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
            canv.drawRightString(page_w - x, y, lines[0])
            y -= size + 4

            for t in lines[1:]:
                canv.drawRightString(page_w - x, y, t)
                y -= size + 4

        merchant = tx.merchant or "ACCOUNT BOOK"
        amount = _money_int(tx.amount)
        occurred = tx.occurred_at.strftime("%Y-%m-%d %H:%M:%S")

        canv.setFont(font_name, 12)
        canv.drawString(x, y, merchant)
        y -= 18

        canv.setFont(font_name, 24)
        canv.drawString(x, y, f"{amount:,}원")
        y -= 20

        # ✅ 계좌 출력 (마스킹)
        last4 = str(account.account_number)[-4:] if account.account_number else "----"
        masked = f"****{last4}" if last4 != "----" else "----"
        canv.setFont(font_name, 10)
        canv.drawString(x, y, f"{account.bank} ({masked})")
        y -= 12

        line()

        approval_no = str(tx.id).zfill(8)
        kv("승인 일시", occurred)
        kv("승인 번호", approval_no)
        kv("거래유형", "승인" if tx.tx_type == Transaction.OUT else "입금")
        kv("할부", "일시불")

        line()

        supply, vat, fee = _calc_vat(amount)
        kv("공급가액", f"{supply:,}원")
        kv("부가세", f"{vat:,}원")
        kv("봉사료", f"{fee:,}원")

        line()

        product_name = tx.product_name or (tx.product.name if tx.product else "상품")
        qty = tx.quantity or 1
        kv("상품명", f"{product_name} ({qty}개)")
        kv("메모", tx.memo or "-")

        line()

        # ✅ 주소 출력 추가 (기본 배송지 기준)
        #    - 기본배송지 없으면 "-" 출력
        if default_addr:
            addr_text = f"({default_addr.zip_code}) {default_addr.address} {default_addr.detail_address}"
        else:
            addr_text = "-"

        kv_multiline("배송지", addr_text, size=7, max_chars=24)

        line()

        canv.setFont(font_name, 7)
        canv.drawString(x, 12 * mm, "※ 본 영수증은 시스템에서 생성된 증빙용 문서입니다.")
        canv.showPage()
        canv.save()

        return resp
