from django.db.models import Avg, Q
from django.views.generic import DetailView, ListView

from shop.models import Category, Coupon, Product, Transaction



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
            OUT_TYPES = ["OUT", "buy"]

            has_bought = Transaction.objects.filter(
            user=self.request.user,
            tx_type__in=OUT_TYPES,  # ✅ 이렇게
            ).filter(
            Q(product=product) | Q(product_name=product.name)
            ).exists()

            already_reviewed = product.reviews.filter(user=self.request.user).exists()

            can_review = has_bought and not already_reviewed

        context["can_review"] = can_review
        return context