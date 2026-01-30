from django.contrib import admin
from .models import Account, Category, Product, Transaction
# Register your models here.
admin.site.register(Account)
admin.site.register(Category)
admin.site.register(Transaction)
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # 어드민 목록 화면에서 보여줄 항목들
    list_display = ('name', 'price', 'stock', 'category')

    # 상세 수정 화면을 구역별로 나누기
    fieldsets = (
        ('기본 정보', {
            'fields': ('category', 'name', 'price', 'stock', 'description')
        }),
        ('상단 슬라이드 이미지 (최대 5장)', {
            'fields': ('image1', 'image2', 'image3', 'image4', 'image5')
        }),
        ('하단 상세 설명 구성', {
            'fields': (
                'description_text1', 'description_image1',
                'description_text2', 'description_image2'
            )
        }),
    )