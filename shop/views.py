from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import *

from .models import Cart, Category, Product, Transaction
from account.models import Account, Address

# ✅ 다계좌(기본 계좌) 대응: 결제/체크아웃은 항상 기본 계좌를 사용
from account.utils.common import get_default_account


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
    """
    장바구니 결제 실행 (예외 처리 강화 버전)
    """

    # LoginRequiredMixin이 로그인이 안 된 사용자를 자동으로 로그인 페이지로 보냅니다.
    login_url = "/accounts/login/"

    def post(self, request):
        # 1. 계좌 정보 확인 (Account 객체 자체가 없는 경우 대비)
        # ✅ 다계좌 대응: 기본 계좌 우선
        user_account = get_default_account(request.user)

        if not user_account:
            messages.error(
                request, "결제 가능한 계좌 정보가 없습니다. 관리자에게 문의하세요."
            )
            return redirect("cart_list")

        # 2. 장바구니 품목 가져오기
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.error(request, "결제할 상품이 장바구니에 없습니다.")
            return redirect("cart_list")

        # 3. 총 결제 금액 계산
        total_price = sum(item.total_price() for item in cart_items)

        try:
            with transaction.atomic():
                # (1) 잔액 검증: 돈이 모자라는 경우
                if user_account.balance < total_price:
                    # 사용자에게 더 친절한 메시지 전달
                    diff = total_price - user_account.balance
                    raise Exception(
                        f"잔액이 {diff:,}원 부족합니다. (현재 잔액: {user_account.balance:,}원)"
                    )

                # (2) 상품별 재고 검증 및 차감
                for item in cart_items:
                    target_product = item.product

                    # 재고가 부족한 경우
                    if target_product.stock < item.quantity:
                        raise Exception(
                            f"[{target_product.name}] 상품의 재고가 부족합니다. (남은 수량: {target_product.stock}개)"
                        )

                    # 실제 재고 차감
                    target_product.stock -= item.quantity
                    target_product.save()

                    # (3) 거래 내역(Transaction) 데이터 생성
                    Transaction.objects.create(
                        user=request.user,
                        account=user_account,
                        product=target_product,
                        product_name=target_product.name,  # 상품 삭제 대비
                        quantity=item.quantity,
                        tx_type=Transaction.OUT,
                        amount=item.total_price(),
                        occurred_at=timezone.now(),
                        memo=f"장바구니 구매: {target_product.name}",
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
            messages.error(request, f"결제 실패: {str(e)}")
            return redirect("cart_list")


class DirectPurchaseView(LoginRequiredMixin, View):
    """
    상세 페이지에서 '바로 구매' 버튼을 눌렀을 때 실행
    """

    def post(self, request, product_id):
        # 1. 대상 상품 및 계좌 확인
        target_product = get_object_or_404(Product, id=product_id)

        # ✅ 다계좌 대응: 기본 계좌 우선
        user_account = get_default_account(request.user)

        # 수량 가져오기 (HTML의 <input name="quantity"> 값)
        buy_quantity = int(request.POST.get("quantity", 1))
        total_price = target_product.price * buy_quantity

        address_id = request.POST.get("address_id")
        delivery_memo = request.POST.get("memo", "메모 없음")

        if not user_account:
            messages.error(request, "결제 가능한 계좌 정보가 없습니다.")
            return redirect("product_detail", pk=product_id)

        # 2. 결제 로직 (트랜잭션)
        try:
            with transaction.atomic():
                # (1) 잔액 검증
                if user_account.balance < total_price:
                    raise Exception(
                        f"잔액이 부족합니다. (현재 잔액: {user_account.balance:,}원)"
                    )

                # (2) 재고 검증
                if target_product.stock < buy_quantity:
                    raise Exception(
                        f"재고가 부족합니다. (현재 재고: {target_product.stock}개)"
                    )

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
                    memo=f"바로구매({address_id}): {delivery_memo}",
                )

                # (5) 잔액 차감
                user_account.balance -= total_price
                user_account.save()

            messages.success(
                request,
                f"[{target_product.name}] {buy_quantity}개 결제가 완료되었습니다!",
            )
            return redirect("mypage")

        except Exception as e:
            messages.error(request, f"결제 실패: {str(e)}")
            return redirect("product_detail", pk=product_id)


class TransactionHistoryView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "shop/transaction_list.html"
    context_object_name = "transactions"

    def get_queryset(self):
        # 로그인한 사용자의 내역만 최신순으로 가져오기
        # 기본적으로 로그인한 사용자의 내역만 가져옴
        queryset = Transaction.objects.filter(user=self.request.user).order_by("-occurred_at")

        # 날짜 필터링 (start_date, end_date)
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date and end_date:
            # 날짜 범위 필터링 (__date__range 사용)
            queryset = queryset.filter(occurred_at__date__range=[start_date, end_date])

        # 계좌 필터링
        account_id = self.request.GET.get("account")
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # 카테고리 필터링
        category_id = self.request.GET.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 필터링에 필요한 목록 데이터
        # ✅ 기본 계좌가 위로 보이도록 정렬 (UX 개선)
        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("-is_default", "-id")
        context["categories"] = Category.objects.all()

        # 탭 상태 결정 (필터가 하나라도 걸려있으면 'out' 탭 유지)
        filter_params = ["start_date", "end_date", "account", "category"]  # 검색 조건들
        if any(self.request.GET.get(param) for param in filter_params) or self.request.GET.get("tab") == "out":
            context["active_tab"] = "out"  # out = 출금
        else:
            context["active_tab"] = "in"  # in = 입금

        # 사용자가 입력한 값들을 다시 템플릿으로 전달 (Input창에 값 유지용)
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["selected_account"] = self.request.GET.get("account", "")
        context["selected_category"] = self.request.GET.get("category", "")

        return context


class CheckoutView(LoginRequiredMixin, View):
    """
    최종 결제 전, 배송지와 주문 내역을 확인하고 수량을 조절하는 페이지
    """

    def post(self, request):
        # 계좌 및 주소지 정보 가져오기
        # ✅ 다계좌 대응: 기본 계좌 우선
        user_account = get_default_account(request.user)

        addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-id")

        if not user_account:
            messages.error(request, "결제 계좌가 없습니다. 마이페이지에서 먼저 등록해 주세요.")
            return redirect("mypage")

        # --- 수량 변경 로직 (주문서 페이지 내에서 +/- 조절 시) ---
        update_item_id = request.POST.get("update_item_id")
        action = request.POST.get("action")

        if update_item_id and action:
            # 장바구니 모델명이 'Cart'인 것을 확인했습니다.
            item = get_object_or_404(Cart, id=update_item_id, user=request.user)
            if action == "increase" and item.quantity < item.product.stock:
                item.quantity += 1
            elif action == "decrease" and item.quantity > 1:
                item.quantity -= 1
            item.save()

        # --- 데이터 구성 (상세페이지 발 vs 장바구니 발) ---
        product_id = request.POST.get("product_id")

        if product_id:
            # 바로 구매 경로
            product = get_object_or_404(Product, id=product_id)
            quantity = int(request.POST.get("quantity", 1))
            total_amount = product.price * quantity
            cart_items = None
        else:
            # 장바구니 결제 경로
            cart_items = Cart.objects.filter(user=request.user)
            if not cart_items.exists():
                messages.error(request, "결제할 상품이 없습니다.")
                return redirect("cart_list")
            total_amount = sum(item.total_price() for item in cart_items)
            product = None
            quantity = None

        context = {
            # ✅ 템플릿 호환: checkout.html에서 'account'를 쓰는 경우가 많음
            "account": user_account,
            "addresses": addresses,
            "product": product,
            "quantity": quantity,
            "cart_items": cart_items,
            "total_amount": total_amount,
        }
        return render(request, "shop/checkout.html", context)

    # 단순 URL 접속 시 장바구니로 리다이렉트
    def get(self, request):
        return redirect("cart_list")
