from decimal import Decimal
from typing import Optional, Tuple
from ..models import UserCoupon


def get_valid_user_coupon(user, selected_coupon_id: Optional[str]) -> Optional[UserCoupon]:
    """
    selected_coupon_id가 None/'None'/빈문자/공백/잘못된 값일 수 있으므로 안전하게 처리해서
    사용 가능한(UserCoupon.is_used=False) 쿠폰만 반환.
    """
    if not selected_coupon_id:
        return None

    cid = str(selected_coupon_id).strip()
    if not cid or cid.lower() == "none":
        return None

    try:
        return (
            UserCoupon.objects.filter(id=cid, user=user, is_used=False)
            .select_related("coupon")
            .first()
        )
    except (ValueError, TypeError):
        return None


def calculate_discount(total_amount, user_coupon: Optional[UserCoupon]) -> Decimal:
    """
    total_amount(Decimal 권장) 기준으로 쿠폰 할인액만 계산해서 반환.
    - min_purchase_amount 조건
    - amount / percentage
    - max_discount_amount 캡
    """
    if not user_coupon:
        return Decimal("0")

    coupon = user_coupon.coupon
    discount_amount = Decimal("0")

    if total_amount < coupon.min_purchase_amount:
        return Decimal("0")

    if coupon.discount_type == "amount":
        discount_amount = Decimal(str(coupon.discount_value))
    else:
        discount_amount = total_amount * (Decimal(str(coupon.discount_value)) / Decimal("100"))
        if coupon.max_discount_amount and discount_amount > coupon.max_discount_amount:
            discount_amount = Decimal(str(coupon.max_discount_amount))

    return discount_amount


def apply_coupon_discount(
    user, total_amount, selected_coupon_id: Optional[str]
) -> Tuple[Decimal, Optional[UserCoupon], Decimal]:
    """
    (discount_amount, user_coupon, final_price) 한번에 반환.
    final_price는 0원 아래로 내려가지 않게 방어.
    """
    user_coupon = get_valid_user_coupon(user, selected_coupon_id)
    discount_amount = calculate_discount(total_amount, user_coupon)
    final_price = max(total_amount - discount_amount, Decimal("0"))
    return discount_amount, user_coupon, final_price
