from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.urls import reverse
from ..models import *
from account.models import Account, Address
from decimal import Decimal  # ✅ Decimal*float 에러 방지용
# ✅ 다계좌(기본 계좌) 대응: 결제/체크아웃은 항상 기본 계좌를 사용
from urllib.parse import urlencode
from ..utils.checkout_util import build_checkout_context


# 체크아웃 페이지
class CheckoutView(LoginRequiredMixin, View):
    """
    최종 결제 전, 배송지와 주문 내역을 확인하고 수량을 조절하는 페이지
    """

    def _get_checkout_context(self, request, product_id=None, quantity=1):
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
    
    def get(self, request):
        # 🌟 [수정 포인트] GET 파라미터에서 정보를 가져와서 context 함수에 넣어줘야 합니다!
        product_id = request.GET.get("product_id")
        quantity = request.GET.get("quantity", 1)
        
        # 이제 단품 구매 정보(ID, 수량)를 포함해서 컨텍스트를 생성합니다.
        context = build_checkout_context(request, product_id, quantity)
        
        # 장바구니도 비어있고, 단품 상품 정보도 없을 때만 장바구니로 보냅니다.
        cart_items = context.get("cart_items")
        has_cart_items = cart_items.exists() if cart_items is not None else False
        has_product = context.get("product") is not None

        if not has_cart_items and not has_product:
            messages.error(request, "결제할 상품이 없습니다.")
            return redirect("cart_list")

            
        return render(request, "shop/checkout.html", context)

    def post(self, request):
        # 수량 변경 로직 (주문서 페이지 내에서 +/- 조절 시)
        update_item_id = request.POST.get("update_item_id")
        action = request.POST.get("action")

        if update_item_id and action:
            item = get_object_or_404(Cart, id=update_item_id, user=request.user)
            if action == "increase" and item.quantity < item.product.stock:
                item.quantity += 1
            elif action == "decrease" and item.quantity > 1:
                item.quantity -= 1
            item.save()
            # 수량 변경 후에는 데이터 갱신을 위해 리다이렉트(GET으로 전환)
            return redirect("checkout")

        # 일반적인 결제 페이지 진입 로직
        product_id = request.POST.get("product_id")
        quantity = request.POST.get("quantity", 1)
        
        context = build_checkout_context(request, product_id, quantity)

        if not context["account"]:
            messages.error(request, "결제 계좌가 없습니다. 마이페이지에서 먼저 등록해 주세요.")
            return redirect("mypage")

        if not context["cart_items"] and not context["product"]:
            messages.error(request, "결제할 상품이 없습니다.")
            return redirect("cart_list")

        # ... (CheckoutView.post 내부, context 만든 뒤 아래 부분만 교체)

        params = {}
        # 단품 결제면 product_id/quantity를 URL에 유지
        if product_id:
            params["product_id"] = product_id
            params["quantity"] = quantity

        # 계좌/쿠폰 선택도 유지
        selected_account_id = request.POST.get("selected_account_id") or request.GET.get("selected_account_id")
        if selected_account_id:
            params["selected_account_id"] = selected_account_id

        selected_coupon_id = request.POST.get("coupon_id") or request.GET.get("coupon_id")
        if selected_coupon_id:
            params["coupon_id"] = selected_coupon_id

        url = reverse("checkout")
        if params:
            url = f"{url}?{urlencode(params)}"

        return redirect(url)