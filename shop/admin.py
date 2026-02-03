from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Category)
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    fields = (
        "user",
        "name",
        "phone",
        "bank",           # ✅ bank_name이 아니라 bank
        "account_number",
        "balance",
        "is_active",
        "created_at",
        "updated_at",
    )
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # 관리자 목록에서 보여줄 칸들
    list_display = ['user', 'product_name', 'quantity', 'tx_type', 'amount', 'occurred_at']
    # 클릭해서 상세 페이지로 들어갈 수 있는 링크 설정
    list_display_links = ['user', 'product_name']
    # 필터링 기능 (입금/출금별로 보기)
    list_filter = ['tx_type', 'occurred_at']

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
admin.site.register(Bank)