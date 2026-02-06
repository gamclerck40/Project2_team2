from django.db import transaction
from account.models import Account
from django.shortcuts import render


def get_default_account(user):
    """
    ✅ 다계좌 구조에서 '대표(기본) 계좌'를 가져오는 표준 함수
    - 기본 계좌(is_default=True)가 있으면 그걸 사용
    - 없으면 가장 최신 계좌 사용
    """
    return (
        Account.objects.filter(user=user, is_default=True).first()
        or Account.objects.filter(user=user).order_by("-id").first()
    )


@transaction.atomic
def set_default_account(user, account_id: int):
    """
    ✅ 기본 계좌 변경 (잔액 이관 포함)
    - 기존 기능(유저의 잔액 wallet 개념)을 유지하기 위해,
      기본 계좌를 바꿀 때 잔액(balance)을 새 기본계좌로 옮긴다.
    - 이렇게 하면 '새 계좌를 기본으로 바꿨더니 잔액이 0이 됨' 문제가 사라짐.
    """
    old_default = (
        Account.objects.select_for_update()
        .filter(user=user, is_default=True)
        .first()
    )
    new_default = (
        Account.objects.select_for_update()
        .filter(user=user, id=account_id)
        .first()
    )

    if not new_default:
        return  # 호출 측에서 존재 여부 체크하지만, 안전장치

    if old_default and old_default.id != new_default.id:
        # ✅ 잔액 이관: 기존 잔액을 새 기본계좌로 이동
        new_default.balance = old_default.balance
        old_default.balance = 0
        old_default.is_default = False
        old_default.save(update_fields=["balance", "is_default"])

        new_default.is_default = True
        new_default.save(update_fields=["balance", "is_default"])

    else:
        # 기존 기본계좌를 다시 기본으로 설정하는 케이스
        Account.objects.filter(user=user, is_default=True).update(is_default=False)
        Account.objects.filter(user=user, id=account_id).update(is_default=True)
    def csrf_failure(request, reason=""):
        return render(request, "errors/csrf_403.html", status=403)