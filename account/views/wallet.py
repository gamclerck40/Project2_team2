from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import Http404

from ..models import Account
from account.utils.common import get_default_account


@login_required
def charge_balance(request):
    if request.method == "POST":
        amount = request.POST.get("amount")

        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            amount_int = 0

        if amount_int > 0:
            # ✅ 다계좌 환경: 기본계좌에 충전
            account = get_default_account(request.user)
            if not account:
                raise Http404("계좌 정보가 없습니다.")

            account.balance += amount_int
            account.save()

    return redirect(request.META.get("HTTP_REFERER", "main"))
