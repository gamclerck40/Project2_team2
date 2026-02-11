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
        "account_number",
        "balance",
        "is_active",
        "created_at",
        "updated_at",
    )

    # ✅ 추가: 목록/검색/필터
    list_display = ("user", "name", "phone", "bank", "account_number", "balance", "is_active", "created_at")
    list_display_links = ("user", "name", "account_number")
    list_filter = ("is_active", "bank", "created_at", "updated_at")  # ✅ 핵심
    search_fields = ("user__username", "user__email", "name", "phone", "account_number")
    ordering = ("-created_at",)


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
