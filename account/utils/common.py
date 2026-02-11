from django.db import transaction
from account.models import Account,Bank
from django.shortcuts import render


def get_default_account(user):
    acc = (
        Account.objects.filter(user=user, is_default=True).first()
        or Account.objects.filter(user=user).order_by("-id").first()
    )
    if acc:
        return acc

    # ✅ 계좌가 아예 없으면 1개 자동 생성 (HTML 수정 없이 안전하게 만들기 위한 정책)
    bank = Bank.objects.first()
    if not bank:
        return None  # 은행도 없으면 생성 못함 (이 경우는 어쩔 수 없이 다른 처리 필요)

    return Account.objects.create(
        user=user,
        name="기본 계좌",
        phone="00000000000",
        bank=bank,
        account_number="0000000000",
        is_default=True,
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
    