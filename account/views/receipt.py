from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from shop.models import Transaction
from account.models import Address
from account.utils.receipt import calc_vat, money_int, register_korean_font

# ✅ 다계좌: 기본계좌 우선
from account.utils.setdefault import get_default_account


@method_decorator(never_cache, name="dispatch")
class ReceiptPDFView(LoginRequiredMixin, View):
    """
    /accounts/receipts/<tx_id>.pdf
    Transaction 1건을 영수증 PDF로 생성

    ✅ 추가: 쿠폰 적용 내역을 PDF에 출력
        쿠폰 이름 : ---
        할인 가격 : ---
        할인 된 가격 : ---
        -----------------------------
        최종 가격 : ---
    """
    login_url = "login"

    def get(self, request, tx_id):
        tx = (
            Transaction.objects
            # ✅ 영수증 "삭제"(숨김)된 건은 PDF 접근도 막음
            .filter(id=tx_id, user=request.user, receipt_hidden=False)
            .select_related("account", "account__bank", "used_coupon", "used_coupon__coupon")
            .first()
        )
        if not tx:
            raise Http404("영수증을 찾을 수 없습니다.")

        account = tx.account
        if not account:
            raise Http404("결제 계좌 정보가 없습니다.")

        # ✅ 기본배송지 fallback (결제 시 저장된 주소가 없을 때만 사용)
        default_addr = Address.objects.filter(user=request.user, is_default=True).first()
        if not default_addr:
            default_addr = Address.objects.filter(user=request.user).first()

        page_w = 80 * mm
        page_h = 110 * mm
        pagesize = portrait((page_w, page_h))

        font_name = register_korean_font()

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
        amount = money_int(tx.amount)
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

        kv("승인일시", occurred)
        kv("거래구분", "출금" if tx.tx_type == Transaction.OUT else "입금")

        # =========================
        # ✅ 쿠폰/할인 내역을 PDF에 출력 (요구사항 포맷)
        # =========================
        discount = money_int(tx.discount_amount)
        coupon_name = "-"
        if tx.used_coupon and getattr(tx.used_coupon, "coupon", None):
            coupon_name = tx.used_coupon.coupon.name or "-"

        original_total = money_int(tx.total_price_at_pay)
        if original_total <= 0:
            # 할인 전 금액이 저장되지 않았다면 최종 + 할인으로 역산
            original_total = amount + discount

        discounted_total = max(original_total - discount, 0)

        if tx.used_coupon or discount > 0:
            kv("쿠폰 이름", coupon_name)
            kv("할인 가격", f"{discount:,}원")
            kv("할인 된 가격", f"{discounted_total:,}원")
            line()
            kv("최종 가격", f"{amount:,}원")
        else:
            kv("최종 가격", f"{amount:,}원")

        line()

        supply, vat, fee = calc_vat(amount)
        kv("공급가액", f"{supply:,}원")
        kv("부가세", f"{vat:,}원")
        kv("봉사료", f"{fee:,}원")

        line()

        product_name = tx.product_name or (tx.product.name if tx.product else "상품")
        qty = tx.quantity or 1
        kv("상품명", f"{product_name} ({qty}개)")
        kv("메모", tx.memo or "-")

        line()

        # ✅ 배송지: 결제 시 Transaction에 저장된 값이 있으면 그걸 우선 출력
        if tx.shipping_address:
            zip_code = tx.shipping_zip_code or ""
            detail = tx.shipping_detail_address or ""
            addr_text = f"({zip_code}) {tx.shipping_address} {detail}".strip()
        elif default_addr:
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


@method_decorator(never_cache, name="dispatch")
class ReceiptHideView(LoginRequiredMixin, View):
    """
    /accounts/receipts/<tx_id>/hide/

    ✅ 요구사항: Transaction(거래내역)은 유지하고, 영수증만 "삭제"(숨김)
    - DB delete() 하지 않음
    - receipt_hidden=True로 처리
    """
    login_url = "login"

    def post(self, request, tx_id):
        tx = (
            Transaction.objects
            .filter(id=tx_id, user=request.user, tx_type=Transaction.OUT)
            .first()
        )
        if not tx:
            raise Http404("삭제할 영수증을 찾을 수 없습니다.")

        tx.receipt_hidden = True
        tx.save(update_fields=["receipt_hidden"])
        messages.success(request, "영수증이 삭제되었습니다. (거래 내역은 유지됩니다)")

        # ✅ 삭제 후 원래 보고 있던 화면으로 복귀(없으면 영수증 탭)
        return redirect(request.META.get("HTTP_REFERER", "/accounts/mypage/?tab=receipt"))
