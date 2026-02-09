from django.db import transaction
from account.models import Account
from django.shortcuts import render


def get_default_account(user):
    return (
        Account.objects.filter(user=user, is_default=True).first()
        or Account.objects.filter(user=user).order_by("-id").first()
    )

@transaction.atomic
def set_default_account(user, account_id: int):
    """
    ✅ 기본 계좌 변경 (잔액 이관 제거 버전)
    - 계좌별 balance를 유지하기 위해, 기본 계좌 플래그만 변경한다.
    - 잔액(balance)은 각 계좌에 그대로 남는다.
    """
    new_default = (
        Account.objects.select_for_update()
        .filter(user=user, id=account_id)
        .first()
    )
    if not new_default:
        return

    # 기존 기본계좌 해제
    Account.objects.filter(user=user, is_default=True).update(is_default=False)
    # 새 기본계좌 지정
    Account.objects.filter(user=user, id=account_id).update(is_default=True)
    