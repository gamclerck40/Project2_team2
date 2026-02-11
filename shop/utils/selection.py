from typing import Optional

from django.shortcuts import get_object_or_404

from account.models import Account, Address
from account.utils.setdefault import get_default_account


def get_selected_account(user, selected_account_id: Optional[str]) -> Optional[Account]:
    """
    주문/결제에서 공통으로 쓰는 계좌 선택 로직.
    - selected_account_id가 있으면 그 계좌(본인 소유 검증)
    - 없으면 기본 계좌(get_default_account)
    """
    if selected_account_id:
        return get_object_or_404(Account, id=selected_account_id, user=user)
    return get_default_account(user)


def get_selected_address(user, address_id: Optional[str]) -> Optional[Address]:
    """
    주문/결제에서 공통으로 쓰는 배송지 선택 로직.
    - address_id 있으면 그 주소(본인 소유 검증)
    - 없으면 기본 배송지
    """
    if address_id:
        return get_object_or_404(Address, id=address_id, user=user)
    return Address.objects.filter(user=user, is_default=True).first()
