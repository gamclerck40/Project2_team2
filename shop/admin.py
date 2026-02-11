from django.contrib import admin
from .models import *
from account.models import *

# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name") if hasattr(Category, "name") else ("id",)
    search_fields = ("name",) if hasattr(Category, "name") else ()
    list_filter = ()  # 필터 걸 필드가 없으면 비워둠
    ordering = ("id",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    # Cart는 보통 user/product/created_at 계열이 있어서 그 기준으로 필터를 거는 게 가장 유용함
    list_display = tuple(x for x in ("id", "user", "product", "quantity") if hasattr(Cart, x)) or ("id",)
    list_filter = tuple(x for x in ("user", "created_at", "updated_at") if hasattr(Cart, x))  # ✅ 핵심
    search_fields = tuple(x for x in ("user__username", "product__name") if True)
    ordering = ("-id",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "product_name",
        "quantity",
        "amount",
        "tx_type",
        "shipping_address",
        "occurred_at",
    )
    list_display_links = ("id", "user", "product_name")
    list_filter = ("tx_type", "category", "occurred_at")  # ✅ 이미 OK
    search_fields = ("user__username", "product_name", "shipping_address", "memo")
    ordering = ("-occurred_at",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "category")

    # ✅ 추가: 필터/검색/정렬
    list_filter = ("category",)  # ✅ 핵심
    search_fields = ("name", "category__name")
    ordering = ("category", "name")

    fieldsets = (
        ("기본 정보", {"fields": ("category", "name", "price", "stock", "description")}),
        ("상단 슬라이드 이미지 (최대 5장)", {"fields": ("image1", "image2", "image3", "image4", "image5")}),
        (
            "하단 상세 설명 구성",
            {"fields": ("description_text1", "description_image1", "description_text2", "description_image2")},
        ),
    )


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "star_rating", "created_at"]
    list_filter = ["rating", "created_at"]  # ✅ 이미 OK
    search_fields = ["content", "user__username", "product__name"]
    inlines = [ReviewImageInline]

    def star_rating(self, obj):
        return "★" * obj.rating
    star_rating.short_description = "평점"


@admin.register(ReviewImage)
class ReviewImageAdmin(admin.ModelAdmin):
    # ✅ ReviewImage도 필터/검색 추가
    list_display = tuple(x for x in ("id", "review", "image") if hasattr(ReviewImage, x)) or ("id",)
    list_filter = tuple(x for x in ("review", "created_at") if hasattr(ReviewImage, x))  # ✅ 핵심
    search_fields = ("review__user__username", "review__product__name")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "discount_type", "discount_value", "valid_to", "active"]
    search_fields = ["name", "code"]

    # ✅ 추가: 필터
    list_filter = ("active", "discount_type", "valid_to")  # ✅ 핵심
    ordering = ("-valid_to",)


@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    list_display = ["user", "coupon", "is_used", "used_at"]

    # ✅ 보강: 필터 확장
    list_filter = ("is_used", "coupon", "user", "used_at")  # ✅ 핵심
    search_fields = ("user__username", "coupon__code", "coupon__name")
    ordering = ("-used_at",)
