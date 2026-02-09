from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils import timezone  # ✅ 추가

# 1. 같은 앱(account) 내 views 폴더와 나란히 있는 models.py에서 Account 가져오기
from ..models import Account
# 2. 다른 앱(shop)의 models.py에서 Cart 모델 가져오기
from shop.models import Cart, Transaction  # ✅ Transaction 추가
from account.utils.common import get_default_account
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import intcomma 

@login_required
def charge_balance(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        account_id = request.POST.get("account_id")        

        # base.html의 모달 폼에서 보낸 현재 페이지 주소 (request.path)
        next_url = request.POST.get("next")

        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            amount_int = 0

        if amount_int > 0:
            # 1. 충전할 계좌 확인
            account = Account.objects.filter(id=account_id, user=request.user).first()
            if not account:
                messages.warning(request, "충전할 계좌를 선택해주세요.")
                return redirect(request.META.get("HTTP_REFERER", "main"))

            # 2. 계좌 잔액 증가
            account.balance += amount_int
            account.save()

            # ✅ [핵심 수정] 충전 내역을 Transaction으로 기록(컨설팅의 입금 합계가 여기서 계산됨)
            Transaction.objects.create(
            # 3. ★ 중요: Transaction(거래내역) 모델에 '입금' 기록 남기기 ★                
                user=request.user,
                account=account,
                category=None,
                product=None,
                quantity=1,
                tx_type=Transaction.IN,        # 모델의 "IN" (입금) 사용
                amount=amount_int,
                occurred_at=timezone.now(),    # 현재 시간
                product_name="계좌 충전",      # 내역에 표시될 상품명
                merchant="내 지갑",            # 거래처
                memo=f"{account.bank.name} 충전 완료"            
            )
            messages.success(request, f"{intcomma(amount_int)}원이 성공적으로 충전되었습니다!")            

        # [리다이렉트 로직]
        # 1순위: next_url이 없다면 이전 페이지(Referer)로 돌아가기
        if next_url:
            return redirect(request.META.get("HTTP_REFERER", "main"))
        else:
            # 2순위: 주문서 등 원래 있던 페이지(next_url)로 돌아가기
            return redirect(next_url)

    # POST 요청이 아닐 경우 메인으로 이동
