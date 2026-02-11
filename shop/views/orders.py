from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.urls import reverse
from django.views.generic import *
from datetime import date
from ..models import *
from decimal import Decimal  # ✅ Decimal*float 에러 방지용
# ✅ 다계좌(기본 계좌) 대응: 결제/체크아웃은 항상 기본 계좌를 사용
from django.db.models import Sum, Case, When, Value, DecimalField, Q
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from urllib.parse import urlencode
from ..utils.selection import get_selected_account, get_selected_address
from ..utils.coupons_util import apply_coupon_discount, get_valid_user_coupon



class OrderExecutionView(LoginRequiredMixin, View):
    def post(self, request):
        # 1. 계좌 선택 로직
        selected_account_id = request.POST.get("selected_account_id")
        user_account = get_selected_account(request.user, selected_account_id)

        # 2. 배송지 정보 가져오기
        address_id = request.POST.get("address_id")
        selected_address = get_selected_address(request.user, address_id)
        
        cart_items = Cart.objects.filter(user=request.user)
        
        if not cart_items.exists():
            messages.error(request, "결제할 상품이 없습니다.")
            return redirect("cart_list")            

        if not selected_address:
            messages.error(request, "배송지 정보가 없습니다. 주소를 등록해주세요.")
            return redirect("cart_list")
        
        if not user_account:
            messages.error(request, "결제 가능한 계좌 정보가 없습니다.")
            return redirect("cart_list")

        # 3. 총 결제 금액 및 쿠폰 할인 계산
        total_price = sum(item.total_price() for item in cart_items)
        
        # --- [수정 구간: 쿠폰 ID 안전하게 가져오기] ---
        selected_coupon_id = request.POST.get("coupon_id")

        discount_amount, user_coupon, final_price = apply_coupon_discount(
            request.user, total_price, selected_coupon_id
        )

        try:
            with transaction.atomic():
                # (1) 잔액 검증
                if user_account.balance < final_price:
                    raise Exception("잔액이 부족합니다.")
                
                now = timezone.now()
                # (2) 상품별 재고 차감 및 거래 내역 생성
                for index, item in enumerate(cart_items):
                    target_product = item.product
                    if target_product.stock < item.quantity:
                        raise Exception(f"[{target_product.name}] 재고 부족")

                    target_product.stock -= item.quantity
                    target_product.save()

                    # 각 상품별 거래 내역 생성 (첫 번째 상품에만 할인 정보를 기록하여 중복 계산 방지)
                    # 혹은 각 상품 가격 비율에 맞춰 할인을 나눌 수 있으나, 단순화를 위해 
                    # 전체 결제 금액(final_price)은 한 번만 잔액에서 깎으므로 로그도 이에 맞춰야 합니다.
                    Transaction.objects.create(
                        user=request.user,
                        account=user_account,
                        product=target_product,
                        product_name=target_product.name,
                        category=target_product.category,
                        quantity=item.quantity,
                        tx_type=Transaction.OUT,
                        # 각 행마다 final_price를 넣으면 총 지출이 (아이템수 * final_price)처럼 보일 수 있음
                        # 여기서는 개별 상품 가격을 적되, 첫 번째 상품 메모에 총 결제 정보를 기록하는 방식 추천
                        amount=item.total_price() if index > 0 else final_price, 
                        total_price_at_pay=total_price if index == 0 else Decimal("0"),
                        discount_amount=discount_amount if index == 0 else Decimal("0"),
                        used_coupon=user_coupon if index == 0 else None,
                        occurred_at=now,
                        shipping_address=selected_address.address,
                        shipping_detail_address=selected_address.detail_address,
                        shipping_zip_code=selected_address.zip_code,
                        receiver_name=selected_address.receiver_name or request.user.username,
                        memo=f"장바구니 결제({index+1}/{cart_items.count()})"
                    )

                # (3) 유저 잔액 차감 (실제 금액 한 번만 차감)
                user_account.balance -= final_price
                user_account.save()

                # (4) 쿠폰 사용 완료 처리
                if user_coupon:
                    user_coupon.is_used = True
                    user_coupon.used_at = now
                    user_coupon.save()

                # (5) 장바구니 비우기
                cart_items.delete()

            messages.success(request, f"결제 완료! 할인금액: {discount_amount:,}원 / 실 결제금액: {final_price:,}원")
            return redirect("mypage")

        except Exception as e:
            messages.error(request, f"결제 실패: {str(e)}")
            return redirect("cart_list")


class DirectPurchaseView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        target_product = get_object_or_404(Product, id=product_id)

        # 1. 계좌 선택
        selected_account_id = request.POST.get("selected_account_id")
        user_account = get_selected_account(request.user, selected_account_id)

        # 2. 배송지 정보
        address_id = request.POST.get("address_id")
        selected_address = get_selected_address(request.user, address_id)
        if not selected_address:
            messages.error(request, "배송지 정보가 없습니다.")
            return redirect("product_detail", pk=product_id)
        
        # 3. 금액 및 쿠폰 계산
        buy_quantity = int(request.POST.get("quantity", 1))
        total_price = target_product.price * buy_quantity

        selected_coupon_id = request.POST.get("coupon_id")
        discount_amount, user_coupon, final_price = apply_coupon_discount(
            request.user, total_price, selected_coupon_id
        )


        try:
            with transaction.atomic():
                # (1) 검증
                if user_account.balance < final_price:
                    raise Exception("잔액 부족")
                if target_product.stock < buy_quantity:
                    raise Exception("재고 부족")

                # (2) 재고 차감
                target_product.stock -= buy_quantity
                target_product.save()

                # (3) 거래 내역 생성 (중복 필드 정리 완료 ✨)
                Transaction.objects.create(
                    user=request.user,
                    account=user_account,
                    product=target_product,
                    category=target_product.category,
                    product_name=target_product.name,
                    quantity=buy_quantity,
                    tx_type=Transaction.OUT,
                    
                    amount=final_price,               # 실제 차감액
                    total_price_at_pay=total_price,    # 할인 전 원가
                    discount_amount=discount_amount,   # 할인액
                    used_coupon=user_coupon,           # 사용 쿠폰
                    
                    occurred_at=timezone.now(),
                    memo=f"바로구매(할인 {discount_amount:,}원): {target_product.name}",
                    shipping_address=selected_address.address,
                    shipping_detail_address=selected_address.detail_address,
                    shipping_zip_code=selected_address.zip_code,
                    receiver_name=selected_address.receiver_name or request.user.username
                )

                # (4) 잔액 차감
                user_account.balance -= final_price
                user_account.save()

                # (5) 쿠폰 사용 완료 처리
                if user_coupon:
                    user_coupon.is_used = True
                    user_coupon.used_at = timezone.now()
                    user_coupon.save()

            messages.success(request, f"결제가 완료되었습니다! (할인금액: {discount_amount:,}원)")
            return redirect("mypage")

        except Exception as e:
            messages.error(request, f"결제 실패: {str(e)}")
            return redirect("product_detail", pk=product_id)