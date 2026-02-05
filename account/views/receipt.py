from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from shop.models import Account, Transaction
from account.utils.receipt import _calc_vat, _money_int, _register_korean_font


@method_decorator(never_cache, name="dispatch")
class ReceiptPDFView(LoginRequiredMixin, View):
    """
    /accounts/receipts/<tx_id>.pdf
    Transaction 1건을 영수증 PDF로 생성
    """
    login_url = "login"

    def get(self, request, tx_id):
        tx = Transaction.objects.filter(id=tx_id, user=request.user).first()
        if not tx:
            raise Http404("영수증을 찾을 수 없습니다.")

        account = Account.objects.filter(user=request.user).first()
        if not account:
            raise Http404("계좌 정보가 없습니다.")

        page_w = 80 * mm
        page_h = 220 * mm
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

        merchant = tx.merchant or "우리 가게"
        amount = _money_int(tx.amount)
        occurred = tx.occurred_at.strftime("%Y-%m-%d %H:%M:%S")

        canv.setFont(font_name, 12)
        canv.drawString(x, y, merchant)
        y -= 18

        canv.setFont(font_name, 24)
        canv.drawString(x, y, f"{amount:,}원")
        y -= 20

        last4 = str(account.account_number)[-4:] if account.account_number else "----"
        canv.setFont(font_name, 10)
        canv.drawString(x, y, f"{account.bank} ({last4})")
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

        canv.setFont(font_name, 7)
        canv.drawString(x, 12 * mm, "※ 본 영수증은 시스템에서 생성된 증빙용 문서입니다.")
        canv.showPage()
        canv.save()

        return resp
