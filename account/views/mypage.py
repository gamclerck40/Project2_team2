import re

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from account.models import * 
from shop.models import *
from account.utils.forms import MypageUpdateForm


@method_decorator(never_cache, name="dispatch")
class MypageView(LoginRequiredMixin, View):
    template_name = "account/mypage.html"
    login_url = "login"
    redirect_field_name = "next"

    def get(self, request):
        # ✅ 비밀번호 인증(10분 유지)
        pw_verified = request.session.get("pw_verified") is True
        pw_verified_at = request.session.get("pw_verified_at")

        if pw_verified and pw_verified_at:
            age = timezone.now().timestamp() - float(pw_verified_at)
            if age > 600:
                request.session.pop("pw_verified", None)
                request.session.pop("pw_verified_at", None)
                pw_verified = False
        else:
            pw_verified = False

        def format_korean_phone(phone: str) -> str:
            if not phone:
                return ""
            digits = re.sub(r"[^0-9]", "", phone)
            if re.match(r"^010\d{7}$", digits):
                return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            if re.match(r"^010\d{8}$", digits):
                return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            return digits

        account = Account.objects.filter(user=request.user).first()
        addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-id")

        formatted_phone = ""
        if account:
            formatted_phone = format_korean_phone(account.phone)

        # ==========================
        # ✅ 영수증 탭: 페이지네이션 + 필터 + 정렬
        # ==========================
        rc_category = (request.GET.get("rc_category") or "").strip()  # category_id
        rc_sort = (request.GET.get("rc_sort") or "newest").strip()    # newest | price_high | price_low
        rc_page = request.GET.get("rc_page") or "1"

        receipts_qs = Transaction.objects.filter(user=request.user, tx_type=Transaction.OUT)

        # 카테고리 필터
        if rc_category.isdigit():
            receipts_qs = receipts_qs.filter(category_id=int(rc_category))

        # 정렬
        if rc_sort == "price_high":
            receipts_qs = receipts_qs.order_by("-amount", "-occurred_at", "-id")
        elif rc_sort == "price_low":
            receipts_qs = receipts_qs.order_by("amount", "-occurred_at", "-id")
        else:
            receipts_qs = receipts_qs.order_by("-occurred_at", "-id")

        # 페이지네이션 (10개)
        paginator = Paginator(receipts_qs, 10)
        receipts_page = paginator.get_page(rc_page)

        receipt_categories = Category.objects.all().order_by("name")

        return render(
            request,
            self.template_name,
            {
                "user_obj": request.user,
                "account": account,
                "addresses": addresses,
                "formatted_phone": formatted_phone,

                # ✅ 영수증 탭
                "receipts_page": receipts_page,
                "receipt_categories": receipt_categories,
                "rc_category": rc_category,
                "rc_sort": rc_sort,

                "pw_verified": pw_verified,
                "banks": Bank.objects.all().order_by("name"),
            },
        )


@method_decorator(never_cache, name="dispatch")
class MypageUpdateView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request):
        form = MypageUpdateForm(request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=edit")

        account = Account.objects.filter(user=request.user).first()
        address_obj = Address.objects.filter(user=request.user, is_default=True).first()

        if not account:
            messages.warning(request, "수정할 계좌 정보가 없습니다. 먼저 계좌를 등록하세요.")
            return redirect("/accounts/mypage/?tab=profile")

        phone = form.cleaned_data["phone"]
        bank = form.cleaned_data["bank"]
        account_number = form.cleaned_data["account_number"]

        zip_code = request.POST.get("zip_code")
        address = request.POST.get("address")
        detail_address = request.POST.get("detail_address")

        new_zip = request.POST.get("new_zip_code")
        new_addr = request.POST.get("new_address")
        new_detail = request.POST.get("new_detail_address")

        try:
            with transaction.atomic():
                if phone != "":
                    account.phone = phone
                if bank is not None:
                    account.bank = bank
                if account_number != "":
                    account.account_number = account_number
                account.save()

                if address_obj:
                    if zip_code:
                        address_obj.zip_code = zip_code
                    if address:
                        address_obj.address = address
                    if detail_address:
                        address_obj.detail_address = detail_address
                    address_obj.save()

                if new_zip and new_addr:
                    Address.objects.create(
                        user=request.user,
                        zip_code=new_zip,
                        address=new_addr,
                        detail_address=new_detail,
                        is_default=False,
                    )
                    messages.success(request, "새 배송지가 추가되었습니다.")

        except IntegrityError:
            messages.warning(request, "이미 사용 중인 계좌번호이거나 저장할 수 없는 값입니다.")
            return redirect("/accounts/mypage/?tab=edit")
        except Exception as e:
            messages.error(request, f"오류가 발생했습니다: {str(e)}")
            return redirect("/accounts/mypage/?tab=edit")

        messages.success(request, "내 정보와 주소가 성공적으로 수정되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
