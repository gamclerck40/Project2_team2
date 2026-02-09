from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.urls import reverse
from django.views.generic import *
from datetime import date
from .models import Cart, Category, Product, Transaction, Review
from account.models import Account, Address
from decimal import Decimal  # ✅ Decimal*float 에러 방지용


# ✅ 다계좌(기본 계좌) 대응: 결제/체크아웃은 항상 기본 계좌를 사용
from account.utils.common import get_default_account
from django.db.models import Sum, Case, When, Value, DecimalField
from django.db.models.functions import TruncMonth


# 상품 목록 페이지(사진,이름,가격 등의 리스트)
class ProductListView(ListView):
    model = Product  # 상품 모델 불러옴
    template_name = "shop/product_list.html"  # html경로
    context_object_name = "products"  # html에서 사용될 이름
    paginate_by = 8  # 한 페이지에 보여질 상품 개수

    def get_queryset(self):
        # 1. 모든 상품을 일단 가져옴
        qs = Product.objects.all()

        # 2. 검색어 가져오기 ("search")
        # .strip()을 통해 앞뒤 공백을 제거해줌
        q = (self.request.GET.get("search") or "").strip()
        category_id = self.request.GET.get("category")
        sort_option = self.request.GET.get("sort", "newest")

        # 1. 검색어 필터링
        if q:
            qs = qs.filter(name__icontains=q)

        # 2. 카테고리 필터링 (DB의 id값과 비교)
        if category_id:
            qs = qs.filter(category_id=category_id)

        # 3. 정렬
        if sort_option == "price_low":
            qs = qs.order_by("price")
        elif sort_option == "price_high":
            qs = qs.order_by("-price")
        else:
            qs = qs.order_by("-id")  # 기본 값

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # DB에 있는 모든 카테고리를 가져와서 템플릿에 'categories'라는 이름으로 전달
        context["categories"] = Category.objects.all()
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
        # ✅ 다계좌 대응: 기본 계좌 우선
        # ✅ [수정] 사용자가 선택한 계좌 ID를 가져옵니다.
        selected_account_id = request.POST.get('selected_account_id')
        
        if selected_account_id:
            user_account = get_object_or_404(Account, id=selected_account_id, user=request.user)
        else:
            user_account = get_default_account(request.user)

        # --- 배송지 정보 가져오기 (기존 코드 유지) ---
        address_id = request.POST.get('address_id') # HTML select name 확인 필요 (아래 팁 참고)

        if address_id:
            selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        else:
            # 주소 ID가 안 넘어왔을 경우 기본 배송지를 자동으로 선택
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

        # 3. 총 결제 금액 계산
        total_price = sum(item.total_price() for item in cart_items)

        try:
            with transaction.atomic():
                if user_account.balance < total_price:
                    raise Exception(f"잔액 부족")
                
                for item in cart_items:
                    target_product = item.product

                    if target_product.stock < item.quantity:
                        raise Exception(f"[{target_product.name}] 재고 부족")

                    target_product.stock -= item.quantity
                    target_product.save()

                    # --- [수정] 이제 selected_address가 정의되어 있으므로 사용 가능 ---
                    Transaction.objects.create(
                        user=request.user,
                        account=user_account,
                        product=target_product,
                        product_name=target_product.name,
                        category=item.product.category,
                        quantity=item.quantity,
                        tx_type=Transaction.OUT,
                        amount=item.total_price(),
                        occurred_at=timezone.now(),
                        memo=f"장바구니 구매: {target_product.name}",
                        shipping_address=selected_address.address,
                        shipping_detail_address=selected_address.detail_address,
                        shipping_zip_code=selected_address.zip_code,
                    )

                # (4) 유저 잔액 차감
                user_account.balance -= total_price
                user_account.save()

                # (5) 장바구니 비우기
                cart_items.delete()

            messages.success(
                request, f"성공적으로 결제되었습니다! ({total_price:,}원 차감)"
            )
            return redirect("mypage")

        except Exception as e:
            # 모든 에러 메시지를 사용자에게 알림으로 전달
            messages.success(request, f"결제가 완료되었습니다!")
            return redirect("cart_list")


class DirectPurchaseView(LoginRequiredMixin, View):
    """
    상세 페이지에서 '바로 구매' 버튼을 눌렀을 때 실행
    """
    def post(self, request, product_id):
        # 1. 대상 상품 및 계좌 확인
        target_product = get_object_or_404(Product, id=product_id)

        # ✅ [수정] 사용자가 선택한 계좌 ID를 가져옵니다.
        selected_account_id = request.POST.get('selected_account_id')
        
        if selected_account_id:
            user_account = get_object_or_404(Account, id=selected_account_id, user=request.user)
        else:
            user_account = get_default_account(request.user)

        # --- 배송지 정보 가져오기 (기존 코드 유지) ---
        address_id = request.POST.get('address_id')
        if address_id:
            selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        else:
            selected_address = Address.objects.filter(user=request.user, is_default=True).first()

        if not selected_address:
            messages.error(request, "배송지 정보가 없습니다.")
            return redirect("product_detail", pk=product_id)
        # ----------------------------------        
        # 수량 가져오기 (HTML의 <input name="quantity"> 값)
        buy_quantity = int(request.POST.get("quantity", 1))
        total_price = target_product.price * buy_quantity

        # 2. 결제 로직 (트랜잭션)
        try:
            with transaction.atomic():
                # (1) 잔액 검증
                if user_account.balance < total_price:
                    raise Exception("잔액 부족")

                # (2) 재고 검증
                if target_product.stock < buy_quantity:
                    raise Exception("재고 부족")

                # (3) 재고 차감 및 저장
                target_product.stock -= buy_quantity
                target_product.save()

                # (4) 거래 내역 생성 (상품 삭제 대비 product_name 포함)
                Transaction.objects.create(
                    user=request.user,
                    account=user_account,
                    product=target_product,
                    category=target_product.category,
                    product_name=target_product.name,
                    quantity=buy_quantity,
                    tx_type=Transaction.OUT,
                    amount=total_price,
                    occurred_at=timezone.now(),
                    # memo=f"바로구매: {target_product.name}",
                    memo=f"바로구매: {target_product.name}",
                    shipping_address=selected_address.address,
                    shipping_detail_address=selected_address.detail_address,
                    shipping_zip_code=selected_address.zip_code,
                )

                # (5) 잔액 차감
                user_account.balance -= total_price
                user_account.save()

            messages.success(request, "결제가 완료되었습니다!")
            return redirect("mypage")

        except Exception as e:
            messages.error(request, f"결제 실패: {str(e)}")
            return redirect("product_detail", pk=product_id)


class TransactionHistoryView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "shop/transaction_list.html"
    context_object_name = "transactions"

    def get_queryset(self):
        queryset = Transaction.objects.filter(user=self.request.user).order_by("-occurred_at")

        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        if start_date and end_date:
            queryset = queryset.filter(occurred_at__date__range=[start_date, end_date])

        account_id = self.request.GET.get("account")
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        category_id = self.request.GET.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("-is_default", "-id")
        context["categories"] = Category.objects.all()

        # ✅ 탭 상태
        tab = (self.request.GET.get("tab") or "in").strip().lower()
        filter_params = ["start_date", "end_date", "account", "category"]

        if tab in ("in", "out", "summary"):
            context["active_tab"] = tab
        elif any(self.request.GET.get(param) for param in filter_params):
            context["active_tab"] = "out"
        else:
            context["active_tab"] = "in"

        qs = context["transactions"]  # 기본 필터(기간/계좌/카테고리)가 이미 적용된 결과
        context["tx_in"] = qs.filter(tx_type=Transaction.IN)
        context["tx_out"] = qs.filter(tx_type=Transaction.OUT)
        context["tx_all"] = qs

        # ✅ totals (현재 qs 기준: 기본 필터까지 포함)
        total_in = context["tx_in"].aggregate(s=Sum("amount"))["s"] or 0
        total_out = context["tx_out"].aggregate(s=Sum("amount"))["s"] or 0
        context["total_in"] = total_in
        context["total_out"] = total_out
        context["net_total"] = total_in - total_out

        # ==============================
        # ✅ [요약/통계 전용 필터] 월 범위 + 지출 카테고리
        # ==============================
        sum_start = (self.request.GET.get("sum_start") or "").strip()   # YYYY-MM
        sum_end = (self.request.GET.get("sum_end") or "").strip()       # YYYY-MM
        sum_category = (self.request.GET.get("sum_category") or "").strip()  # category id or ""

        context["sum_start"] = sum_start
        context["sum_end"] = sum_end
        context["sum_category"] = sum_category

        summary_qs = qs  # 기본필터 + summary필터를 반영할 queryset

        # ✅ 월 범위 필터 (occurred_at 기준)
        # - YYYY-MM -> 해당 월 1일~말일 범위로 변환해서 적용
        def _parse_ym(s):
            # "2026-02" -> (2026, 2)
            y, m = s.split("-")
            return int(y), int(m)

        if sum_start:
            y, m = _parse_ym(sum_start)
            summary_qs = summary_qs.filter(occurred_at__date__gte=date(y, m, 1))

        if sum_end:
            y, m = _parse_ym(sum_end)
            # 다음달 1일을 구해서 lt로 제한
            if m == 12:
                ny, nm = y + 1, 1
            else:
                ny, nm = y, m + 1
            summary_qs = summary_qs.filter(occurred_at__date__lt=date(ny, nm, 1))

        # ✅ 월별 수익/지출 (summary_qs 기준)
        monthly = (
            summary_qs.annotate(m=TruncMonth("occurred_at"))
            .values("m")
            .annotate(
                in_sum=Sum(Case(
                    When(tx_type=Transaction.IN, then="amount"),
                    default=Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=0),
                )),
                out_sum=Sum(Case(
                    When(tx_type=Transaction.OUT, then="amount"),
                    default=Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=0),
                )),
            )
            .order_by("m")
        )

        labels, in_values, out_values = [], [], []
        for row in monthly:
            if not row.get("m"):
                continue
            labels.append(row["m"].strftime("%Y-%m"))
            in_values.append(int(row.get("in_sum") or 0))
            out_values.append(int(row.get("out_sum") or 0))

        context["chart_labels"] = "|".join(labels)
        context["chart_in"] = "|".join(map(str, in_values))
        context["chart_out"] = "|".join(map(str, out_values))

        # ✅ 카테고리별 지출(OUT) - summary_qs 기준
        out_qs = summary_qs.filter(tx_type=Transaction.OUT)

        # sum_category가 있으면 해당 카테고리만 (원하면 “전체에서 선택한 카테고리 강조”로 바꿀 수도 있음)
        if sum_category:
            out_qs = out_qs.filter(category_id=sum_category)

        by_cat = (
            out_qs.values("category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        cat_labels = []
        cat_values = []
        for row in by_cat:
            cat_labels.append(row["category__name"] or "미분류")
            cat_values.append(int(row["total"] or 0))

        context["cat_chart_labels"] = "|".join(cat_labels)
        context["cat_chart_values"] = "|".join(map(str, cat_values))

        # 기본 필터 유지용
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["selected_account"] = self.request.GET.get("account", "")
        context["selected_category"] = self.request.GET.get("category", "")

        return context
class CheckoutView(LoginRequiredMixin, View):
    """
    최종 결제 전, 배송지와 주문 내역을 확인하고 수량을 조절하는 페이지
    """

    def _get_checkout_context(self, request, product_id=None, quantity=1):
    # 1. 여기서 변수를 먼저 정의해야 합니다!
        all_accounts = Account.objects.filter(user=request.user, is_active=True).select_related('bank')
        
        # ✅ 사용자가 selectbox에서 선택한 계좌 ID 확인
        selected_account_id = request.GET.get('selected_account_id') or request.POST.get('selected_account_id')
        
        if selected_account_id:
            user_account = all_accounts.filter(id=selected_account_id).first()
        else:
            user_account = all_accounts.filter(is_default=True).first() or all_accounts.first()

        addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-id")

        # 상품 및 금액 로직
        if product_id:
            # 바로 구매 경로
            product = get_object_or_404(Product, id=product_id)
            total_amount = product.price * int(quantity)
            cart_items = None
        else:
            cart_items = Cart.objects.filter(user=request.user)
            total_amount = sum(item.total_price() for item in cart_items) if cart_items.exists() else 0
            product = None
            quantity = None

        return {
            "account": user_account,    # 결제 요약용 (단일)
            "accounts": all_accounts,
            "addresses": addresses,
            "product": product,
            "quantity": quantity,
            "cart_items": cart_items,
            "total_amount": total_amount,
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

        return render(request, "shop/checkout.html", context)
class ReviewCreateView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)

        # 1. 실구매자 인증 (보안 강화)
        has_purchased = Transaction.objects.filter(
            user=request.user, 
            product=product, 
            tx_type=Transaction.OUT
        ).exists()

        if not has_purchased:
            messages.error(request, "해당 상품을 구매하신 분만 리뷰를 남길 수 있습니다.")
            return redirect("product_detail", pk=product_id)

        if Review.objects.filter(user=request.user, product=product).exists():
            messages.warning(request, "이미 이 상품에 대한 리뷰를 작성하셨습니다.")
            return redirect("product_detail", pk=product_id)
        # 2. 데이터 가져오기
        content = request.POST.get("content")
        rating = request.POST.get("rating")

        if not content or not rating:
            messages.error(request, "내용과 평점을 모두 입력해주세요.")
            return redirect("product_detail", pk=product_id)

        # 3. 리뷰 생성
        Review.objects.create(
            product=product,
            user=request.user,
            rating=int(rating),
            content=content
        )

        messages.success(request, "리뷰가 등록되었습니다!")
        return redirect("product_detail", pk=product_id)

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

        # 3. 데이터 업데이트 및 저장
        if content and rating:
            review.content = content
            review.rating = int(rating)
            review.save()
            messages.success(request, "리뷰가 성공적으로 수정되었습니다.")
        else:
            messages.error(request, "내용과 평점을 모두 입력해주세요.")

        # 4. 상세 페이지의 리뷰 섹션으로 다시 리다이렉트
        return redirect(reverse('product_detail', kwargs={'pk': product_id}) + '#review-section')
class ConsultingProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "shop/product_consulting_list.html"
    context_object_name = "products"
    paginate_by = 8

    def _month_range(self):
        today = timezone.localdate()
        start = today.replace(day=1)
        return start, today

    def _calc_month_net(self):
        start, end = self._month_range()

        qs = Transaction.objects.filter(
            user=self.request.user,
            occurred_at__date__gte=start,
            occurred_at__date__lte=end,
        )

        # ✅ Decimal 연산 안정성: 기본값도 Decimal("0")
        total_in = qs.filter(tx_type=Transaction.IN).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        total_out = qs.filter(tx_type=Transaction.OUT).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return total_in, total_out, (total_in - total_out)

    def _recommend_budget(self, balance, month_net):
        """
        ✅ 여기서 발생한 에러(Decimal * float) 근본 원인 제거:
        - float 상수(0.30 등)를 전부 Decimal("0.30")로 변경
        - balance/month_net이 int/None일 수 있는 경우도 방어
        """
        if balance is None:
            balance = Decimal("0")
        if month_net is None:
            month_net = Decimal("0")

        if not isinstance(balance, Decimal):
            balance = Decimal(str(balance))
        if not isinstance(month_net, Decimal):
            month_net = Decimal(str(month_net))

        if month_net > 0:
            budget = (balance * Decimal("0.30")) + (month_net * Decimal("0.20"))
        else:
            budget = balance * Decimal("0.15")

        budget = min(budget, balance)

        # ✅ 원 단위로 정리 (템플릿 intcomma 출력과도 잘 맞음)
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

        # ✅ 기본 계좌 기준 자산/예산 산정
        default_account = get_default_account(self.request.user)
        balance = default_account.balance if default_account else Decimal("0")

        _, _, month_net = self._calc_month_net()
        budget = self._recommend_budget(balance, month_net)

        # ✅ 예산 이하 상품만 노출
        qs = qs.filter(price__lte=budget)

        # ✅ 정렬 옵션은 product_list와 동일하게 유지(구조/사용감 일치)
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

        default_account = get_default_account(self.request.user)
        balance = default_account.balance if default_account else Decimal("0")

        total_in, total_out, month_net = self._calc_month_net()
        budget = self._recommend_budget(balance, month_net)

        context["default_account"] = default_account
        context["balance"] = balance
        context["month_total_in"] = total_in
        context["month_total_out"] = total_out
        context["month_net"] = month_net
        context["recommended_budget"] = budget

        # ✅ 컨설팅 멘트(컨셉용)
        if month_net > 0:
            context["consult_msg"] = "이번 달은 흑자 흐름이에요. 추천 예산 안에서 부담 없는 소비를 제안할게요."
        else:
            context["consult_msg"] = "이번 달은 지출이 많은 편이에요. 당분간은 가성비/필수 위주로 추천할게요."

        return context
