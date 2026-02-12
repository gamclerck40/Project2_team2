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
        "bank",
        "account_number",   # ✅ 상세에서 원본 확인 가능
        "balance",
        "is_active",
        "is_default",
        "created_at",
        "updated_at",
    )

    # ✅ list_display에서 account_number 대신 마스킹 컬럼 사용
    list_display = (
        "user",
        "name",
        "phone",
        "bank",
        "masked_account_number_admin",
        "balance",
        "is_active",
        "is_default",
        "created_at",
    )
    list_display_links = ("user", "name")
    list_filter = ("is_active", "is_default", "bank", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "name", "phone", "account_number")
    ordering = ("-created_at",)

    @admin.display(description="계좌번호(마스킹)")
    def masked_account_number_admin(self, obj: Account):
        return obj.masked_account_number()


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    # ✅ Bank도 필터/검색/정렬 추가
    list_display = ("id", "name") if hasattr(Bank, "name") else ("id",)
    search_fields = ("name",) if hasattr(Bank, "name") else ()
    list_filter = ()  # Bank는 보통 필터 걸 필드가 적어서 비워두되, 아래처럼 모델에 필드 있으면 추가 가능
    ordering = ("id",)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("alias", "user", "zip_code", "address", "detail_address", "is_default")
    list_display_links = ("alias", "user", "address")
    list_filter = ("is_default", "user")  # ✅ 이미 잘 되어 있음
    search_fields = ("user__username", "address", "detail_address", "alias")
