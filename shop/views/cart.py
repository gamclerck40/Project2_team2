from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView

from shop.models import Cart, Product




# 장바구니 추가
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


# 장바구니 목록 페이지
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


# 장바구니 제거
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
