from decimal import Decimal
from django.shortcuts import get_object_or_404
from account.models import Account, Address
from ..models import Cart, Product, UserCoupon


def build_checkout_context(request, product_id=None, quantity=1):
    # 1. 여기서 변수를 먼저 정의해야 합니다!
    all_accounts = Account.objects.filter(user=request.user, is_active=True).select_related('bank')
        
        # 계좌 선택 로직
    selected_account_id = request.GET.get('selected_account_id') or request.POST.get('selected_account_id')
        
    if selected_account_id:
            user_account = all_accounts.filter(id=selected_account_id).first()
    else:
        user_account = all_accounts.filter(is_default=True).first() or all_accounts.first()

    addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-id")
    user_coupons = UserCoupon.objects.filter(user=request.user, is_used=False).select_related('coupon')
    # ✅ 쿠폰 ID 가져오기 (이게 있어야 아래 if selected_coupon_id 가 작동함)
    selected_coupon_id = request.GET.get('coupon_id')

    # 상품 및 기본 금액 계산
    if product_id:
        product = get_object_or_404(Product, id=product_id)
        total_amount = product.price * int(quantity)
        cart_items = None
    else:

        product = None
        quantity = None
        cart_items = Cart.objects.filter(user=request.user)
        total_amount = sum(item.total_price() for item in cart_items) if cart_items.exists() else Decimal("0")

        # ✅ 쿠폰 할인 로직 (변수명 total_amount로 통일)
    discount_amount = Decimal("0")
    if selected_coupon_id:
        user_coupon = user_coupons.filter(id=selected_coupon_id).first()
        if user_coupon:
            coupon = user_coupon.coupon
            if total_amount >= coupon.min_purchase_amount:
                if coupon.discount_type == 'amount':
                    discount_amount = Decimal(str(coupon.discount_value))
                else:
                    discount_amount = total_amount * (Decimal(str(coupon.discount_value)) / Decimal("100"))
                    if coupon.max_discount_amount and discount_amount > coupon.max_discount_amount:
                        discount_amount = Decimal(str(coupon.max_discount_amount))

    final_price = total_amount - discount_amount
    return {
        "account": user_account,    # 결제 요약용 (단일)
        "accounts": all_accounts,
        "addresses": addresses,
        "product": product,
        "quantity": quantity,
        "cart_items": cart_items,
        "total_amount": total_amount,
        "discount_amount": discount_amount,
        "final_price": final_price,
        "user_coupons": user_coupons,
        "selected_coupon_id": selected_coupon_id,            
    }