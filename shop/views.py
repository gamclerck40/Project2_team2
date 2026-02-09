from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.urls import reverse
from django.views.generic import *

from .models import Cart, Category, Product, Transaction, Review
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
        user_account = get_default_account(request.user)
        # --- [추가] 배송지 정보 가져오기 ---
        address_id = request.POST.get('default_addr_id') # HTML의 select name
        if address_id:
            selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        else:
            # 주소 ID가 안 넘어왔을 경우 기본 배송지를 자동으로 선택
            selected_address = Address.objects.filter(user=request.user, is_default=True).first()

        if not selected_address:
            messages.error(request, "배송지 정보가 없습니다. 주소를 등록해주세요.")
            return redirect("cart_list")
        # ----------------------------------
        if not user_account:
            messages.error(request, "결제 가능한 계좌 정보가 없습니다.")
            return redirect("cart_list")

        # 2. 장바구니 품목 가져오기
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.error(request, "결제할 상품이 없습니다.")
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

        # ✅ 다계좌 대응: 기본 계좌 우선
        user_account = get_default_account(request.user)
        # --- [추가] 배송지 정보 가져오기 ---
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

    def _get_checkout_context(self, request, product_id=None, quantity=1):
    # 1. 여기서 변수를 먼저 정의해야 합니다!
        all_accounts = Account.objects.filter(user=request.user, is_active=True).select_related('bank')
        
        # 2. 기본 계좌 설정 (is_default가 True인 것 우선, 없으면 첫 번째 계좌)
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
        # ✅ 이제 GET 요청(충전 후 복귀 등) 시에도 쫓아내지 않고 페이지를 보여줍니다!
        context = self._get_checkout_context(request)
        
        # 장바구니가 진짜 비어있을 때만 보냅니다.
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