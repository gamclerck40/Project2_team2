from django.contrib import admin

from .models import *
from account.models import *

# Register your models here.
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    fields = (
        "user",
        "name",
        "phone",
        "bank",  # ✅ bank_name이 아니라 bank
        "account_number",
        "balance",
        "is_active",
        "created_at",
        "updated_at",
    )
admin.site.register(Bank)
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    # 관리자 목록 화면에서 보여줄 필드들
    list_display = ('alias','user', 'zip_code', 'address', 'detail_address', 'is_default')
    # 클릭하면 수정 페이지로 이동할 필드
    list_display_links = ('alias','user', 'address')
    # 필터 기능을 사용할 필드 (유저별로 보거나 기본 배송지만 모아보기 편리함)
    list_filter = ('is_default', 'user')
    # 검색 기능 (유저 아이디나 주소로 검색 가능)
    search_fields = ('user__username', 'address', 'detail_address')
