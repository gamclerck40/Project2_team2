from django.contrib import admin

from .models import *
from account.models import *

# Register your models here.
admin.site.register(Category)
admin.site.register(Cart)
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):

    # 1. 목록에서 보여줄 컬럼들 (주소 추가)
    list_display = (
        'id', 
        'user', 
        'product_name', 
        'quantity', 
        'amount', 
        'tx_type', 
        'shipping_address',  # 추가된 주소 필드
        'occurred_at'
    )

    # 2. 클릭 시 상세 페이지로 이동할 항목
    list_display_links = ('id', 'user', 'product_name')

    # 3. 우측 필터 바 설정
    list_filter = ('tx_type', 'category', 'occurred_at')

    # 4. 검색창 설정 (주소로도 검색 가능)
    search_fields = ('user__username', 'product_name', 'shipping_address', 'memo')

    # 5. 최신순으로 정렬해서 보기 (선택 사항)
    ordering = ('-occurred_at',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # 어드민 목록 화면에서 보여줄 항목들
    list_display = ("name", "price", "stock", "category")

    # 상세 수정 화면을 구역별로 나누기
    fieldsets = (
        (
            "기본 정보",
            {"fields": ("category", "name", "price", "stock", "description")},
        ),
        (
            "상단 슬라이드 이미지 (최대 5장)",
            {"fields": ("image1", "image2", "image3", "image4", "image5")},
        ),
        (
            "하단 상세 설명 구성",
            {
                "fields": (
                    "description_text1",
                    "description_image1",
                    "description_text2",
                    "description_image2",
                )
            },
        ),
    )

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    # 'rating'(숫자) 대신 'star_rating'(별모양 함수)을 목록에 표시합니다.
    list_display = ['product', 'user', 'star_rating', 'created_at'] 
    list_filter = ['rating', 'created_at']
    search_fields = ['content', 'user__username', 'product__name']

    def star_rating(self, obj):
        return "★" * obj.rating
    star_rating.short_description = "평점"