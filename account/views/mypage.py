import re

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from account.models import Account, Address, Bank
from shop.models import Transaction, Category
from account.utils.forms import MypageUpdateForm, AccountAddForm

# ✅ 잔액 이관 포함 set_default_account 사용
from account.utils.common import get_default_account, set_default_account


#내 정보 뷰(Main)
@method_decorator(never_cache, name="dispatch")
class MypageView(LoginRequiredMixin, View):
    template_name = "account/mypage.html"
    login_url = "login"
    redirect_field_name = "next"

    def get(self, request): # 세션 (Key) 생성.
        # ✅ 비밀번호 인증(10분 유지)
        # 세션에 'pw_verified = True일 때 인증됨 상태로 판단.
        pw_verified = request.session.get("pw_verified") is True

        # 인증된 시간을 세션에서 가져옴.
        pw_verified_at = request.session.get("pw_verified_at")

        # 인증 상태 = True, 인증 시각도 저장되어 있으면 아래 시간 체크 시작.
        if pw_verified and pw_verified_at:
            age = timezone.now().timestamp() - float(pw_verified_at)
            #600초 = 10분 지났으면 인증 만료 처리.
            if age > 60:
                #만료 된 키들을 삭제 (None 처리)
                request.session.pop("pw_verified", None)
                request.session.pop("pw_verified_at", None)
                # 코드 내부 상태도 False로 전환.
                pw_verified = False

        #pw_verified, pw_verified_at이 없으면 인증 안 된 상태로 둠.
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

        accounts = Account.objects.filter(user=request.user).order_by("-is_default", "-id")
        address_list = Address.objects.filter(user=request.user).order_by("-is_default", "id")
    
        addr_page_num = request.GET.get("addr_page") or "1" # 주소 전용 페이지 파라미터
        addr_paginator = Paginator(address_list, 5)        # 5개씩 제한
        addresses_page = addr_paginator.get_page(addr_page_num)
        # ✅ “현재 선택 계좌(=기본계좌)”를 프로젝트 전체 정책과 동일하게 통일
        account = get_default_account(request.user)
        default_account = account
        
        formatted_phone = ""
        if default_account:
            formatted_phone = format_korean_phone(default_account.phone)

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

        paginator = Paginator(receipts_qs, 10)
        receipts_page = paginator.get_page(rc_page)

        receipt_categories = Category.objects.all().order_by("name")

        # ==========================
        # ✅ 요약 통계 탭: 누적 전체 지출/수익 합계
        # ==========================
        total_out = (
            Transaction.objects.filter(user=request.user, tx_type=Transaction.OUT)
            .aggregate(s=Sum("amount"))
            .get("s")
            or 0
        )
        total_in = (
            Transaction.objects.filter(user=request.user, tx_type=Transaction.IN)
            .aggregate(s=Sum("amount"))
            .get("s")
            or 0
        )
        net_total = total_in - total_out

        # ✅ 기존 기능을 해치지 않게: 폼은 그대로 두되, 템플릿에서 쓰는 경우만 사용
        account_add_form = AccountAddForm()

        return render(
            request,
            self.template_name,
            {
                "user_obj": request.user,

                # ✅ 기존 템플릿 호환
                "account": account,

                # ✅ 다계좌(추가 기능이 아니라 계좌번호 정책 변경의 필수 데이터)
                "accounts": accounts,
                "default_account": default_account,
                "account_add_form": account_add_form,

                "addresses": addresses_page,
                "formatted_phone": formatted_phone,

                # ✅ 영수증 탭
                "receipts_page": receipts_page,
                "receipt_categories": receipt_categories,
                "rc_category": rc_category,
                "rc_sort": rc_sort,

                # ✅ 요약 통계 탭
                "total_out": total_out,
                "total_in": total_in,
                "net_total": net_total,

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

        # ✅ 기존 first() 대신: 기본계좌를 수정 대상으로 사용(정책 일관)
        account = Account.objects.filter(user=request.user).first()
        addr_ids = request.POST.getlist("address_id[]")
        aliases = request.POST.getlist("address_alias[]")
        zip_codes = request.POST.getlist("zip_code[]")
        addresses = request.POST.getlist("address[]")
        detail_addresses = request.POST.getlist("detail_address[]")

        if not account:
            messages.warning(request, "수정할 계좌 정보가 없습니다. 먼저 계좌를 등록하세요.")
            return redirect("/accounts/mypage/?tab=profile")

        phone = form.cleaned_data["phone"]
        bank = form.cleaned_data["bank"]
        account_number = form.cleaned_data["account_number"]

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

                for a_id, alias, z_code, addr, d_addr in zip(
                    addr_ids, aliases, zip_codes, addresses, detail_addresses
                ):
                    target_addr = Address.objects.filter(id=a_id, user=request.user).first()
                    if target_addr:
                        target_addr.alias = alias
                        target_addr.zip_code = z_code
                        target_addr.address = addr
                        target_addr.detail_address = d_addr
                        target_addr.save()

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


@method_decorator(never_cache, name="dispatch")
class SetDefaultAccountView(LoginRequiredMixin, View):
    def post(self, request, account_id):
        # 존재/권한 체크
        if not Account.objects.filter(id=account_id, user=request.user).exists():
            messages.warning(request, "계좌를 찾을 수 없습니다.")
            return redirect("/accounts/mypage/?tab=profile")

        # ✅ 잔액 이관 포함 기본계좌 변경
        set_default_account(request.user, account_id)
        messages.success(request, "기본 계좌가 변경되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")


@method_decorator(never_cache, name="dispatch")
class AccountAddView(LoginRequiredMixin, View):
    def post(self, request):
        form = AccountAddForm(request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=profile")

        bank = form.cleaned_data["bank"]
        acc = form.cleaned_data["account_number"]

        # 기본 계좌가 없으면 첫 등록 계좌를 기본으로
        has_default = Account.objects.filter(user=request.user, is_default=True).exists()

        # ✅ 기존 기능(잔액 wallet 개념) 유지:
        # 새 계좌를 추가할 때 잔액을 0으로 만들면,
        # 기본계좌를 새 계좌로 바꾸는 순간 잔액이 0처럼 보여서 "balance가 무쓸모"가 된다.
        # 따라서 현재 기본계좌 잔액을 복사해둔다.
        base = get_default_account(request.user)
        base_name = (base.name if base else request.user.username)
        base_phone = (base.phone if base else "")

        try:
            with transaction.atomic():
                Account.objects.create(
                    user=request.user,
                    name=base_name,
                    phone=base_phone,
                    bank=bank,
                    account_number=acc,

                    # ✅ 계좌별 잔액 분리: 신규 계좌는 0원 시작(또는 필요 시 입력받아 세팅)
                    balance=0,

                    is_active=True,
                    is_default=(not has_default),
                )
            messages.success(request, "계좌가 추가되었습니다.")
        except IntegrityError:
            messages.warning(request, "이미 등록된 계좌입니다.")
        return redirect("/accounts/mypage/?tab=profile")


@method_decorator(never_cache, name="dispatch")
class AccountDeleteView(LoginRequiredMixin, View):
    def post(self, request, account_id):
        acc = Account.objects.filter(id=account_id, user=request.user).first()
        if not acc:
            messages.warning(request, "삭제할 계좌가 없습니다.")
            return redirect("/accounts/mypage/?tab=profile")

        if acc.is_default:
            messages.warning(request, "기본 계좌는 삭제할 수 없습니다.")
            return redirect("/accounts/mypage/?tab=profile")

        acc.delete()
        messages.success(request, "계좌가 삭제되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
