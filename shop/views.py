from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.urls import reverse
from django.views.generic import *
from datetime import date
from .models import *
from account.models import Account, Address
from decimal import Decimal  # ✅ Decimal*float 에러 방지용
# ✅ 다계좌(기본 계좌) 대응: 결제/체크아웃은 항상 기본 계좌를 사용
from account.utils.common import get_default_account
from django.db.models import Sum, Case, When, Value, DecimalField, Q
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from urllib.parse import urlencode


# 상품 목록 페이지(사진,이름,가격 등의 리스트)
class ProductListView(ListView):
    model = Product
    template_name = "shop/product_list.html"
    context_object_name = "products"
    paginate_by = 8

    def get_queryset(self):
        # ... 기존 코드 그대로 유지 ...
        qs = Product.objects.all()
        q = (self.request.GET.get("search") or "").strip()
        category_id = self.request.GET.get("category")
        sort_option = self.request.GET.get("sort", "newest")

        if q:
            qs = qs.filter(name__icontains=q)
        if category_id:
            qs = qs.filter(category_id=category_id)

        if sort_option == "price_low":
            qs = qs.order_by("price")
        elif sort_option == "price_high":
            qs = qs.order_by("-price")
        else:
            qs = qs.order_by("-id")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 1. 모든 카테고리 가져오기 (기존 코드)
        context["categories"] = Category.objects.all()
        context["display_coupon"] = Coupon.objects.filter(active=True).order_by("-id")

        return context


# 상품의 상세 페이지 (상세 설명, 남은 개수)
class ProductDetailView(DetailView):
    model = Product
    template_name = "shop/product_detail.html"
    context_object_name = "product"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()

        # [수정 부분] URL 파라미터에서 edit_id를 가져와 컨텍스트에 추가
        edit_id = self.request.GET.get('edit_id')
        if edit_id:
            context['edit_review_id'] = int(edit_id)

        # 1. 이 상품에 달린 리뷰들 최신순으로 가져오기
        reviews = product.reviews.all().order_by('-created_at')
        context["reviews"] = reviews

        # 2. 평균 별점 계산 (리뷰가 없으면 0)
        from django.db.models import Avg
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        context["average_rating"] = round(avg_rating, 1) if avg_rating else 0

        # 3. 실구매자 여부 확인
        can_review = False
        if self.request.user.is_authenticated:
            can_review = Transaction.objects.filter(
                user=self.request.user, 
                product=product, 
                tx_type=Transaction.OUT
            ).exists()
        context["can_review"] = can_review

        return context

# 장바구니 담기 기능을 처리하는 클래스 기반 view
class AddToCartView(View):
    def post(self, request, product_id):
        # 1. 담으려는 상품 정보를 DB에서 가져옴
        # 로그인 체크
        if not request.user.is_authenticated:
            messages.error(request, "장바구니는 로그인 후 이용 가능합니다.")
            return redirect("login")  # 혹은 상세페이지로 리다이렉트

        # 1. 담으려는 상품 정보를 DB에서 가져옴
        product = get_object_or_404(Product, id=product_id)

        # 2. 사용자가 선택한 수량을 가져옴 기본 1개
        quantity = int(request.POST.get("quantity", 1))

        # 3. 해당 상품이 장바구니에 있는지 확인, 없으면 생성
        cart_item, created = Cart.objects.get_or_create(
            user=request.user, product=product, defaults={"quantity": 0}
        )

        # 재고 체크, 장바구니에 담긴 수량+새로 담을 수량이 재고를 초과할 시
        if cart_item.quantity + quantity > product.stock:
            messages.warning(
                request,
                f"죄송합니다. 현재 재고가 부족합니다. (잔여 재고: {product.stock}개)",
            )
            # 경고 warning 메세지 생성 사용자에게 재고 부족을 알림

            return redirect("cart_list")

        # 성공 로직 재고가 충분하면 수량을 더하고 DB에 저장
        cart_item.quantity += quantity
        cart_item.save()

        # 성공 메세지 생성 상품이 담겼음을 의미함
        messages.success(
            request, f"{product.name} 상품 {quantity}개가 장바구니에 담겼습니다."
        )

        return redirect("cart_list")


# Cart에선 제너릭 뷰가 아니라 view를 쓰는 이유는 장바구니는 데이터를 보여주는게 핵심이 아닌 특정 동작(저장)을 처리하는것이 핵심 이기 때문임
# 장바구니는 따져야할 요소가 많기 때문에 if로직을 자유롭게 사용할려면 post함수를 짤 수 있는 일반 view가 편하고 자유로움


# 장바구니 목록을 리스트 형태로 보여주는 view
class CartListView(ListView):
    model = Cart
    template_name = "shop/cart_list.html"
    context_object_name = "cart_items"

    # 1. 화면에 보여줄 데이터를 가져오는 규칙에 대한 함수
    def get_queryset(self):
        # 모든 사람이 장바구니를 보면 보안에 문제가 될 수 있음
        # filter를 사용하여 현재 로그인 한 유저(self.request.user)의 물건만 골라냄
        return Cart.objects.filter(user=self.request.user)

    # 2. 목록 외에 추가로 화면에 전달할 데이터 (총 금액)을 계산
    def get_context_data(self, **kwargs):
        # 부모 클래스(list_view)가 기본적으로 준비한 데이터를 먼저 가져옴 (context)
        context = super().get_context_data(**kwargs)

        # 위에서 필터링한 장바구니 물건들을 한번 더 가져옴
        cart_items = self.get_queryset()

        # 장바구니에 담긴 모든 물건의 (수량 * 가격)을 합산
        total = sum(item.total_price() for item in cart_items)

        # 계산된 합계를 total_amount에 담아 html로 전송
        context["total_amount"] = total

        # 데이터가 담긴 context를 최종 반환함
        return context


# 장바구니 아이템의 수량을 변경,품목 삭제하는 다목적 뷰
class RemoveFromCartView(View):
    # 사용자가 +/- 버튼 또는 삭제 버튼을 눌렀을때 post 방식으로 실행됨
    def post(self, request, cart_item_id):

        # 1. 수정하려는 장바구니 상품이 실제 유저의 것인지 확인 후 가져옴
        cart_item = get_object_or_404(Cart, id=cart_item_id, user=request.user)

        # html에서 보낸 mode값을 읽어옴 (increase, derease등)
        mode = request.POST.get("mode")

        # 수량 감소 로직
        if mode == "decrease":
            # 수량이 1보다 클 때만 깎아 0개가 되지 않게 보호
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()  # 변경 수량 저장

        # 수량 증가 로직
        elif mode == "increase":
            # 상품의 재고(stock)를 넘지 않을 때만 증가(재고 초과 방지)
            if cart_item.quantity < cart_item.product.stock:
                cart_item.quantity += 1
                cart_item.save()

            else:
                # 재고가 부족할 때 처리를 하고 싶다면 여기에 추가 (생략 가능)
                pass
        # 품목 삭제 로직
        # 모드 값이 아예 없거나(삭제 버튼),다른 값일 경우 실행
        else:
            # 장바구니에서 해당 상품을 완전히 제거
            cart_item.delete()
        # 모든 처리가 끝난 후 장바구니 화면으로 이동
        return redirect("cart_list")


class OrderExecutionView(LoginRequiredMixin, View):
    def post(self, request):
        # 1. 계좌 선택 로직
        selected_account_id = request.POST.get('selected_account_id')
        if selected_account_id:
            user_account = get_object_or_404(Account, id=selected_account_id, user=request.user)
        else:
            user_account = get_default_account(request.user)

        # 2. 배송지 정보 가져오기
        address_id = request.POST.get('address_id')
        if address_id:
            selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        else:
            selected_address = Address.objects.filter(user=request.user, is_default=True).first()
        
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
        selected_coupon_id = request.POST.get('coupon_id')
        discount_amount = Decimal("0")
        user_coupon = None

        if selected_coupon_id and selected_coupon_id.strip() and selected_coupon_id != 'None':
            try:
                user_coupon = UserCoupon.objects.filter(
                    id=selected_coupon_id, 
                    user=request.user, 
                    is_used=False
                ).select_related('coupon').first()
                
                if user_coupon:
                    coupon = user_coupon.coupon
                    if total_price >= coupon.min_purchase_amount:
                        if coupon.discount_type == 'amount':
                            discount_amount = Decimal(str(coupon.discount_value))
                        else: # percentage
                            discount_amount = total_price * (Decimal(str(coupon.discount_value)) / Decimal("100"))
                            if coupon.max_discount_amount and discount_amount > coupon.max_discount_amount:
                                discount_amount = Decimal(str(coupon.max_discount_amount))
            except (ValueError, TypeError):
                user_coupon = None
        # ----------------------------------------------

        final_price = max(total_price - discount_amount, Decimal("0"))

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
        selected_account_id = request.POST.get('selected_account_id')
        if selected_account_id:
            user_account = get_object_or_404(Account, id=selected_account_id, user=request.user)
        else:
            user_account = get_default_account(request.user)

        # 2. 배송지 정보
        address_id = request.POST.get('address_id')
        if address_id:
            selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        else:
            selected_address = Address.objects.filter(user=request.user, is_default=True).first()

        if not selected_address:
            messages.error(request, "배송지 정보가 없습니다.")
            return redirect("product_detail", pk=product_id)
        
        # 3. 금액 및 쿠폰 계산
        buy_quantity = int(request.POST.get("quantity", 1))
        total_price = target_product.price * buy_quantity
        selected_coupon_id = request.POST.get('coupon_id')
        discount_amount = Decimal("0")
        user_coupon = None

        # 'None' 문자열이거나 빈 값인 경우를 제외하고 실행
        if selected_coupon_id and selected_coupon_id != 'None':
            user_coupon = UserCoupon.objects.filter(
                id=selected_coupon_id, 
                user=request.user, 
                is_used=False
            ).select_related('coupon').first()

            # ✅ 이 부분이 if selected_coupon_id 안에 있어야 안전합니다.
            if user_coupon:
                coupon = user_coupon.coupon
                if total_price >= coupon.min_purchase_amount:
                    if coupon.discount_type == 'amount':
                        discount_amount = Decimal(str(coupon.discount_value))
                    else: # percentage
                        discount_amount = total_price * (Decimal(str(coupon.discount_value)) / Decimal("100"))
                        if coupon.max_discount_amount and discount_amount > coupon.max_discount_amount:
                            discount_amount = Decimal(str(coupon.max_discount_amount))

        # 최종 가격 계산 (할인액 반영)
        final_price = max(total_price - discount_amount, Decimal("0"))

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


class TransactionHistoryView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "shop/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 10  # ✅ 10개씩 페이징 적용

    def get_queryset(self):
        # 1. 기본 쿼리셋
        queryset = Transaction.objects.filter(user=self.request.user).order_by("-occurred_at")
        tab = self.request.GET.get("tab", "in").strip().lower()

        # 2. 공통 필터링 (입금/출금 공통으로 날짜와 계좌 필터 적용) ✨
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        if start_date and end_date:
            queryset = queryset.filter(occurred_at__date__range=[start_date, end_date])

        account_id = self.request.GET.get("account")
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # 3. 탭별 특화 필터링
        if tab == "in":
            queryset = queryset.filter(tx_type=Transaction.IN)

        elif tab == "out":
            queryset = queryset.filter(tx_type=Transaction.OUT)

            # 출금 탭 전용 카테고리 필터
            category_id = self.request.GET.get("category")
            if category_id:
                queryset = queryset.filter(category_id=category_id)

            # ✅ 할인 적용된 거래만 보기(쿠폰 사용 or 할인금액 존재)
            discounted = (self.request.GET.get("discounted") or "").strip()
            if discounted == "1":
                queryset = queryset.filter(Q(discount_amount__gt=0) | Q(used_coupon__isnull=False))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 기본 필터 데이터
        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("-is_default", "-id")
        context["categories"] = Category.objects.all()

        # 탭 상태
        tab = self.request.GET.get("tab", "in").strip().lower()
        context["active_tab"] = tab

        # ✅ 기존 요약/통계 로직 (그대로 유지)
        qs = Transaction.objects.filter(user=self.request.user)
        total_in = qs.filter(tx_type=Transaction.IN).aggregate(s=Sum("amount"))["s"] or 0
        total_out = qs.filter(tx_type=Transaction.OUT).aggregate(s=Sum("amount"))["s"] or 0
        context["total_in"] = total_in
        context["total_out"] = total_out
        context["net_total"] = total_in - total_out

        # [요약/통계 차트 전용 로직]
        sum_start = (self.request.GET.get("sum_start") or "").strip()
        sum_end = (self.request.GET.get("sum_end") or "").strip()
        sum_category = (self.request.GET.get("sum_category") or "").strip()
        context["sum_start"] = sum_start
        context["sum_end"] = sum_end
        context["sum_category"] = sum_category

        summary_qs = qs

        def _parse_ym(s):
            y, m = s.split("-")
            return int(y), int(m)

        # ✅ 월 범위 필터는 summary_qs에만 적용 (그래프/카테고리집계 공용)
        if sum_start:
            y, m = _parse_ym(sum_start)
            summary_qs = summary_qs.filter(occurred_at__date__gte=date(y, m, 1))
        if sum_end:
            y, m = _parse_ym(sum_end)
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            summary_qs = summary_qs.filter(occurred_at__date__lt=date(ny, nm, 1))

        # ✅ [추가] 상단 총 수익/지출/순이익도 summary_qs(필터 조건) 기준으로 표시되도록 덮어쓰기
        total_in = summary_qs.filter(tx_type=Transaction.IN).aggregate(s=Sum("amount"))["s"] or 0
        total_out = summary_qs.filter(tx_type=Transaction.OUT).aggregate(s=Sum("amount"))["s"] or 0
        context["total_in"] = total_in
        context["total_out"] = total_out
        context["net_total"] = total_in - total_out

        # ✅ (핵심) 그래프는 "항상 1개 막대"로 합쳐서 표시
        #    - 필터 없으면: 전체
        #    - 필터 있으면: YYYY-MM~YYYY-MM 집계
        label = "전체"
        if sum_start or sum_end:
            # 둘 중 하나만 있어도 보기 좋은 라벨로
            if sum_start and sum_end:
                if sum_start == sum_end:
                    label = f"{sum_start} 집계"
                else:
                    label = f"{sum_start} ~ {sum_end} 집계"
            elif sum_start and not sum_end:
                label = f"{sum_start}~ 집계"
            elif (not sum_start) and sum_end:
                label = f"~{sum_end} 집계"

        # ✅ 필터된 summary_qs 기준으로 총합만 계산해서 1개로 전달
        period_in = summary_qs.filter(tx_type=Transaction.IN).aggregate(s=Sum("amount"))["s"] or 0
        period_out = summary_qs.filter(tx_type=Transaction.OUT).aggregate(s=Sum("amount"))["s"] or 0

        context["chart_labels"] = label
        context["chart_in"] = str(int(period_in or 0))
        context["chart_out"] = str(int(period_out or 0))

        # ✅ 카테고리별 지출 통계는 기존 로직대로 유지 (월필터 적용된 summary_qs 사용)
        out_qs = summary_qs.filter(tx_type=Transaction.OUT)
        if sum_category:
            out_qs = out_qs.filter(category_id=sum_category)

        by_cat = out_qs.values("category__name").annotate(total=Sum("amount")).order_by("-total")
        cat_labels, cat_values = [], []
        for row in by_cat:
            cat_labels.append(row["category__name"] or "미분류")
            cat_values.append(int(row["total"] or 0))

        context["cat_chart_labels"] = "|".join(cat_labels)
        context["cat_chart_values"] = "|".join(map(str, cat_values))

        # 필터 유지용
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["selected_account"] = self.request.GET.get("account", "")
        context["selected_category"] = self.request.GET.get("category", "")
        context["discounted"] = self.request.GET.get("discounted", "")
        context["has_summary_data"] = summary_qs.exists()
        context["has_category_data"] = bool(cat_labels)
        return context
    
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
        context = self._get_checkout_context(request, product_id, quantity)
        
        # 장바구니도 비어있고, 단품 상품 정보도 없을 때만 장바구니로 보냅니다.
        if not context["cart_items"] and not context["product"]:
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
        
        context = self._get_checkout_context(request, product_id, quantity)

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
class ReviewCreateView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)

        # 1. 구매 여부 확인
        has_purchased = Transaction.objects.filter(
            user=request.user, 
            product=product, 
            tx_type=Transaction.OUT
        ).exists()

        if not has_purchased:
            messages.error(request, "해당 상품을 구매하신 분만 리뷰를 남길 수 있습니다.")
            return redirect("product_detail", pk=product.id)
        # 2. 리뷰 데이터 가져오기        
        rating = request.POST.get('rating')
        content = request.POST.get('content')

        # 3. 리뷰 본문 생성 (먼저 생성해야 review 객체의 ID가 생김)
        review = Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            content=content
        )

        # 4. 🔥 여러 장의 이미지 처리 (핵심 부분)
        # request.FILES.getlist를 사용하여 선택된 모든 파일을 리스트로 가져옵니다.
        images = request.FILES.getlist('review_images') 

        for img in images:
        # 파일이 실제로 존재할 때만(빈 칸이 아닐 때만) 저장
            if img:
                ReviewImage.objects.create(review=review, image=img)
        messages.success(request, "리뷰가 성공적으로 등록되었습니다.")
        return redirect("product_detail", pk=product.id)
class ReviewDeleteView(LoginRequiredMixin, View):
    def post(self, request, review_id):
        # 1. 내 리뷰인지 확인하며 가져오기 (보안)
        review = get_object_or_404(Review, id=review_id, user=request.user)
        product_id = review.product.id

        # 2. 삭제 처리
        review.delete()

        # 3. 메시지 남기기
        messages.success(request, "리뷰가 성공적으로 삭제되었습니다.")

        # 4. 상품 상세 페이지의 '리뷰 섹션' 위치로 바로 이동하도록 주소 생성
        # 결과 예시: /shop/products/5/#review-section
        return redirect(reverse('product_detail', kwargs={'pk': product_id}) + '#review-section')


class ReviewUpdateView(LoginRequiredMixin, View):
    def post(self, request, review_id):
        # 1. 내 리뷰인지 확인하며 가져오기 (보안)
        review = get_object_or_404(Review, id=review_id, user=request.user)
        product_id = review.product.id

        # 2. 수정 데이터 가져오기
        content = request.POST.get("content")
        rating = request.POST.get("rating")

        # ✅ 추가된 데이터: 삭제할 이미지 ID 리스트와 새로 등록할 파일들
        delete_image_ids = request.POST.getlist("delete_images")
        new_images = request.FILES.getlist("review_images")

        # 3. 데이터 업데이트 및 저장
        if content and rating:
            review.content = content
            review.rating = int(rating)
            review.save()

            # ✅ [추가] 이미지 삭제 로직
            if delete_image_ids:
                # 선택된 이미지들을 찾아서 한꺼번에 삭제
                # (이때 review.images는 ReviewImage 모델과의 관계 이름입니다)
                review.images.filter(id__in=delete_image_ids).delete()

            # ✅ [추가] 새 이미지 저장 로직
            for img in new_images:
                # ReviewImage 모델을 사용하여 새 객체 생성
                # (모델명이 다를 경우 본인의 모델명에 맞게 수정하세요)
                ReviewImage.objects.create(review=review, image=img)            
            messages.success(request, "리뷰가 성공적으로 수정되었습니다.")
        else:
            messages.error(request, "내용과 평점을 모두 입력해주세요.")

        # 4. 상세 페이지의 리뷰 섹션으로 다시 리다이렉트
        return redirect(reverse('product_detail', kwargs={'pk': product_id}) + '#review-section')
    
class ProductListView(ListView):
    model = Product
    template_name = "shop/product_list.html"
    context_object_name = "products"
    paginate_by = 8

    def get_queryset(self):
        # ... 기존 코드 그대로 유지 ...
        qs = Product.objects.all()
        q = (self.request.GET.get("search") or "").strip()
        category_id = self.request.GET.get("category")
        sort_option = self.request.GET.get("sort", "newest")

        if q:
            qs = qs.filter(name__icontains=q)
        if category_id:
            qs = qs.filter(category_id=category_id)

        if sort_option == "price_low":
            qs = qs.order_by("price")
        elif sort_option == "price_high":
            qs = qs.order_by("-price")
        else:
            qs = qs.order_by("-id")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 1. 모든 카테고리 가져오기 (기존 코드)
        context["categories"] = Category.objects.all()
        context["display_coupon"] = Coupon.objects.filter(active=True).order_by("-id")

        return context

class ConsultingProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "shop/product_consulting_list.html"
    context_object_name = "products"
    paginate_by = 8

    def _month_range(self):
        today = timezone.localdate()
        start = today.replace(day=1)
        return start, today

    def _to_decimal(self, v):
        if v is None:
            return Decimal("0")
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def _calc_month_in(self, account=None):
        """이번 달 입금(IN) 합계
        - account가 주어지면 해당 계좌 기준
        - account가 None이면 ✅ 계좌 상관없이(전체) 기준
        """
        start, end = self._month_range()
        qs = Transaction.objects.filter(
            user=self.request.user,
            occurred_at__date__gte=start,
            occurred_at__date__lte=end,
        )
        if account is not None:
            qs = qs.filter(account=account)

        total_in = qs.filter(tx_type=Transaction.IN).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_in).quantize(Decimal("1"))

    def _calc_month_out(self, account=None):
        """이번 달 출금(OUT) 합계
        - account가 주어지면 해당 계좌 기준
        - account가 None이면 ✅ 계좌 상관없이(전체) 기준
        """
        start, end = self._month_range()
        qs = Transaction.objects.filter(
            user=self.request.user,
            occurred_at__date__gte=start,
            occurred_at__date__lte=end,
        )
        if account is not None:
            qs = qs.filter(account=account)

        total_out = qs.filter(tx_type=Transaction.OUT).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_out).quantize(Decimal("1"))

    def _calc_total_in(self, account=None):
        """누적 입금(IN) 합계(가입 이후 전체)
        - account=None이면 ✅ 계좌 상관없이(전체)
        """
        qs = Transaction.objects.filter(user=self.request.user, tx_type=Transaction.IN)
        if account is not None:
            qs = qs.filter(account=account)

        total_in = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_in).quantize(Decimal("1"))

    def _calc_total_out(self, account=None):
        """누적 출금(OUT) 합계: 가입 이후 전체
        - account=None이면 ✅ 계좌 상관없이(전체)
        """
        qs = Transaction.objects.filter(user=self.request.user, tx_type=Transaction.OUT)
        if account is not None:
            qs = qs.filter(account=account)

        total_out = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_out).quantize(Decimal("1"))

    def _calc_asset_base(self, total_in, total_out):
        """✅ Runway+SWR 모델 계산용 자산(순자산)
        = 누적입금 - 누적출금 (0 미만은 0 처리)
        """
        total_in = self._to_decimal(total_in)
        total_out = self._to_decimal(total_out)
        net = total_in - total_out
        if net < 0:
            net = Decimal("0")
        return net.quantize(Decimal("1"))

    def _recommend_budget(self, asset_base, month_out):
        asset_base = self._to_decimal(asset_base)
        month_out = self._to_decimal(month_out)

        if asset_base <= 0:
            return Decimal("0")

        # 1) runway (months)
        denom = month_out if month_out > 0 else Decimal("1")
        runway = asset_base / denom

        # 2) base monthly safe spending rate (월 1%)
        base_rate = Decimal("0.01")

        # 3) risk multiplier by runway
        if runway >= Decimal("24"):
            mult = Decimal("1.6")
        elif runway >= Decimal("12"):
            mult = Decimal("1.2")
        elif runway >= Decimal("6"):
            mult = Decimal("0.9")
        else:
            mult = Decimal("0.6")

        budget = asset_base * base_rate * mult
        budget = min(budget, asset_base)

        return budget.quantize(Decimal("1"))

    def get_queryset(self):
        qs = Product.objects.all()

        q = (self.request.GET.get("search") or "").strip()
        category_id = self.request.GET.get("category")
        sort_option = self.request.GET.get("sort", "newest")

        if q:
            qs = qs.filter(name__icontains=q)
        if category_id:
            qs = qs.filter(category_id=category_id)

        # ✅ 예산 산정(모델 계산)은 "누적 순자산"을 기반으로,
        # ✅ 분모(소비속도)는 "이번 달 지출"로 유지하는 구성이 가장 자연스러움
        month_out = self._calc_month_out(account=None)
        total_in = self._calc_total_in(account=None)
        total_out = self._calc_total_out(account=None)
        asset_base = self._calc_asset_base(total_in, total_out)
        budget = self._recommend_budget(asset_base, month_out)

        qs = qs.filter(price__lte=budget)

        if sort_option == "price_low":
            qs = qs.order_by("price")
        elif sort_option == "price_high":
            qs = qs.order_by("-price")
        else:
            qs = qs.order_by("-id")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()

        # 월 라벨 ("N월")
        today = timezone.localdate()
        context["month_label"] = f"{today.month}월"

        # 기본계좌(표시용 유지)
        default_account = get_default_account(self.request.user)
        balance = self._to_decimal(default_account.balance if default_account else 0).quantize(Decimal("1"))
        context["default_account"] = default_account
        context["balance"] = balance

        # ✅ 이번 달 기준
        month_in = self._calc_month_in(account=None)
        month_out = self._calc_month_out(account=None)

        # ✅ 누적(전체) 기준
        total_in = self._calc_total_in(account=None)
        total_out = self._calc_total_out(account=None)

        # ✅ 모델 계산(예산/런웨이)용 자산: 누적 순자산
        asset_base = self._calc_asset_base(total_in, total_out)
        budget = self._recommend_budget(asset_base, month_out)

        # -----------------------------------------
        # ✅ 컨텍스트 키 구성 (기존 키 + 신규 키 공존)
        # -----------------------------------------

        # 1) 이번 달 표기용(신규)
        context["month_total_in"] = month_in
        context["month_total_out"] = month_out  # (이번 달 지출)

        # 2) 누적(전체) 표기용(신규)
        context["total_in_all"] = total_in
        context["total_out_all"] = total_out

        # 3) 기존 템플릿 호환용(유지)
        # - 기존에 current_asset을 "총 누적 수익"으로 쓰던 흐름을 깨지 않기 위해 유지
        context["current_asset"] = total_in

        # 추천 예산
        context["recommended_budget"] = budget

        # 런웨이 메시지 (누적 순자산 / 이번 달 지출)
        denom = month_out if month_out > 0 else Decimal("1")
        runway = asset_base / denom

        if runway >= Decimal("24"):
            context["consult_msg"] = "지출 속도 대비 자산 런웨이가 충분합니다. 기준 예산보다 한 단계 적극적으로 제안할게요."
        elif runway >= Decimal("12"):
            context["consult_msg"] = "런웨이가 안정 구간입니다. 무리 없는 범위에서 예산을 제안할게요."
        elif runway >= Decimal("6"):
            context["consult_msg"] = "지출 속도가 자산 대비 빠른 편입니다. 예산을 보수적으로 조정했어요."
        elif month_out == 0:
            context["consult_msg"] = "이번 달 지출이 없어 런웨이가 매우 깁니다. 예산은 자산 대비 보수적으로 제안했어요."
        else:
            context["consult_msg"] = "런웨이가 짧습니다. 당분간은 필수 소비 중심으로 예산을 강하게 제한하는 걸 권합니다."

        return context    
class CouponRegisterView(LoginRequiredMixin, View):
    """
    CBV 방식의 쿠폰 등록 및 목록 조회 뷰
    """
    def get(self, request):
        # 유저가 보유한 쿠폰 목록을 최신순으로 가져옴
        from .models import UserCoupon
        user_coupons = UserCoupon.objects.filter(user=request.user).order_by('-issued_at')
        return render(request, 'shop/register_coupon.html', {
            'user_coupons': user_coupons
        })

    def post(self, request):
        from .models import Coupon, UserCoupon
        code = request.POST.get('coupon_code', '').strip().upper()

        # 1. 존재 여부 확인
        coupon = Coupon.objects.filter(code=code, active=True).first()

        if not coupon:
            messages.error(request, "유효하지 않거나 사용 중지된 쿠폰 코드입니다.")
        # 2. 유효 기간 확인
        elif coupon.valid_to < timezone.now():
            messages.error(request, "사용 기간이 만료된 쿠폰입니다.")
        # 3. 중복 발급 확인
        elif UserCoupon.objects.filter(user=request.user, coupon=coupon).exists():
            messages.warning(request, "이미 등록된 쿠폰입니다.")
        else:
            # 4. 발급 처리
            UserCoupon.objects.create(user=request.user, coupon=coupon)
            messages.success(request, f"🎉 [{coupon.name}] 쿠폰이 성공적으로 등록되었습니다!")

        return redirect('register_coupon')