from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.shortcuts import redirect
from django.utils import timezone

from account.models import Account
from shop.models import Transaction

@login_required
def charge_balance(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        account_id = request.POST.get("account_id")
        # base.html에서 보낸 쿼리스트링이 포함된 전체 주소
        next_url = request.POST.get("next")

        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            amount_int = 0

        if amount_int > 0:
            account = Account.objects.filter(id=account_id, user=request.user).first()
            if not account:
                messages.warning(request, "충전할 계좌를 선택해주세요.")
                return redirect(request.META.get("HTTP_REFERER", "/"))

            # 계좌 잔액 증가
            account.balance += amount_int
            account.save()

            # 거래 내역 기록
            Transaction.objects.create(
                user=request.user,
                account=account,
                tx_type=Transaction.IN,
                amount=amount_int,
                occurred_at=timezone.now(),
                product_name="계좌 충전",
                merchant="내 지갑",
                memo=f"{account.bank.name} 충전 완료"
            )
            messages.success(request, f"{intcomma(amount_int)}원이 성공적으로 충전되었습니다!")

        # [리다이렉트 핵심] 
        # 1. 결제 정보가 포함된 next_url이 있다면 최우선 이동
        if next_url and next_url != "":
            return redirect(next_url.split("#")[0])
        return redirect(request.META.get("HTTP_REFERER", "/"))
    # POST 요청이 아닐 경우 루트 페이지로 이동
    return redirect("/")
