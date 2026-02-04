import re
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views import View
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from shop.models import Account, Transaction, Bank
from .forms import (
    SignUpForm,
    FindIDForm,
    MypageUpdateForm,
    PasswordVerifyForm,PasswordResetVerifyForm, 
)

User = get_user_model()

def csrf_failure(request, reason=""):
    # 403이지만 UX는 "세션이 갱신되었어요. 다시 시도해주세요"로 안내
    return render(request, "errors/csrf_403.html", status=403)

@method_decorator(never_cache, name="dispatch")
class SignUpView(View):
    template_name = "account/signup.html"

    def get(self, request):
        form = SignUpForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = SignUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with transaction.atomic():
                user = form.save()

                Account.objects.create(
                    user=user,
                    name=form.cleaned_data["name"],
                    phone=form.cleaned_data["phone"],
                    bank=form.cleaned_data["bank"],
                    account_number=form.cleaned_data["account_number"],
                    balance=form.cleaned_data["balance"],
                    is_active=True,
                )
        except IntegrityError:
            # phone unique 등에서 터질 수 있음
            form.add_error(None, "이미 사용 중인 정보가 있습니다.")
            return render(request, self.template_name, {"form": form})

        login(request, user)
        return redirect("product_list")

@method_decorator(never_cache, name="dispatch")
class MypageView(LoginRequiredMixin, View):
    template_name = "account/mypage.html"
    login_url = "login"
    redirect_field_name = "next"

    def get(self, request):
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

        formatted_phone = ""
        if account:
            formatted_phone = format_korean_phone(account.phone)

        return render(
            request,
            self.template_name,
            {
                "user_obj": request.user,
                "account": account,
                "formatted_phone": formatted_phone,
                "receipts": [],
                "pw_verified": pw_verified,
                "banks": Bank.objects.all().order_by("name"),
            },
        )

# 계정 찾기 View
@method_decorator(never_cache, name="dispatch")
class FindAccountView(View):
    template_name = "account/find_account.html"

    def get(self, request):
        tab = request.GET.get("tab", "id")

        #다중탭 ID/PW 구분.
        context = {
            "tab": tab,
            "id_form": FindIDForm(),
            "pw_form": PasswordVerifyForm(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        tab = request.POST.get("tab")

        # ✅ ID 찾기
        if tab == "id":
            form = FindIDForm(request.POST)
            # ID 찾기로 넘어온 POST 폼이 유효하지 않을 때.
            if not form.is_valid():
                # 다시 계정 찾기 폼으로 되돌아오며, 
                return render(
                    request,
                    self.template_name,
                    {"tab": "id", "id_form": form, "pw_form": PasswordVerifyForm()},
                )
            
            # [핵심] cleaned_data로 받아 검증된 휴대전화 번호로
            # 그 번호와 맞는 User를 탐색 - 필터링.
            phone = form.cleaned_data["phone"]
            users = User.objects.filter(accounts__phone=phone)

            return render(
                request,
                "account/find_id_result.html",
                {"users": users},
            )

        # ✅ PW 찾기 (1단계 인증)
        if tab == "pw":
            form = PasswordVerifyForm(request.POST)
            #올바르지 않은 비밀번호 입력시 "경고"
            if not form.is_valid():
                messages.warning(request, "비밀번호를 입력해 주세요.")
                return redirect("/accounts/find/?tab=pw")

            pw = form.cleaned_data["current_password"]

            if not request.user.check_password(pw):
                messages.warning(request, "현재 비밀번호가 올바르지 않습니다.")
                return redirect("/accounts/find/?tab=pw")

            request.session["pw_verified"] = True
            request.session["pw_verified_at"] = timezone.now().timestamp()

            return redirect("/accounts/find/password/")
@method_decorator(never_cache, name="dispatch")
class MypageUpdateView(LoginRequiredMixin, View):
    login_url = "login"
    def post(self, request):
        form = MypageUpdateForm(request.POST)

        # 유효하지 않은 폼이 왔을 때, 에러 메세지 출력.
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=edit")

        #해당 사용자에 맞는 Account의 모든 정보 호출.
        account = Account.objects.filter(user=request.user).first()

        # 계정 정보가 없을 때
        if not account:
            messages.warning(request, "수정할 계좌 정보가 없습니다. 먼저 계좌를 등록하세요.")
            return redirect("/accounts/mypage/?tab=profile")

        # 데이터를 유효한 형태로 꺼내기 'cleaned_data'
        phone = form.cleaned_data["phone"]
        bank = form.cleaned_data["bank"]  # ✅ Bank 객체 or None
        account_number = form.cleaned_data["account_number"]

        try:
            with transaction.atomic():
                if phone != "":
                    account.phone = phone
                if bank is not None:
                    account.bank = bank
                if account_number != "":
                    account.account_number = account_number

                account.save()  # ✅ updated_at 자동 갱신
        except IntegrityError:
            messages.warning(request, "이미 사용 중인 계좌번호이거나 저장할 수 없는 값입니다.")
            return redirect("/accounts/mypage/?tab=edit")

        messages.success(request, "내 정보가 수정되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
@method_decorator(never_cache, name="dispatch")
class PasswordResetView(LoginRequiredMixin, View):
    template_name = "account/find_password_reset.html"

    def get(self, request):
        if not request.session.get("pw_verified"):
            messages.warning(request, "먼저 본인 인증을 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        form = SetPasswordForm(user=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = SetPasswordForm(user=request.user, data=request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = form.save()
        update_session_auth_hash(request, user)

        request.session.pop("pw_verified", None)
        request.session.pop("pw_verified_at", None)

        messages.success(request, "비밀번호가 변경되었습니다.")
        return redirect("login")
@method_decorator(never_cache, name="dispatch")
class PasswordResetVerifyView(View):
    """
    PW 찾기 탭: (아이디/이름/계좌번호)로 본인확인
    성공 시 세션에 reset_verified 플래그 + 대상 user_id 저장
    """
    def post(self, request):
        form = PasswordResetVerifyForm(request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            # PW찾기 탭으로 복귀
            return redirect("/accounts/find/?tab=pw")

        # ✅ 인증 성공: 세션 기록
        request.session["reset_verified"] = True
        request.session["reset_verified_at"] = timezone.now().timestamp()
        request.session["reset_user_id"] = form.user.id

        messages.success(request, "본인 확인이 완료되었습니다. 새 비밀번호를 설정해 주세요.")
        return redirect("/accounts/find/?tab=pw")
@method_decorator(never_cache, name="dispatch")   
class PasswordVerifyView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request):
        form = PasswordVerifyForm(request.POST)
        if not form.is_valid():
            messages.warning(request, "비밀번호를 입력해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        pw = form.cleaned_data["current_password"]

        if not request.user.check_password(pw):
            messages.warning(request, "현재 비밀번호가 올바르지 않습니다.")
            return redirect("/accounts/mypage/?tab=edit")

        request.session["pw_verified"] = True
        request.session["pw_verified_at"] = timezone.now().timestamp()

        messages.success(request, "본인 인증이 완료되었습니다. 새 비밀번호를 설정해 주세요.")
        return redirect("/accounts/mypage/?tab=edit")

@method_decorator(never_cache, name="dispatch")
class PasswordChangeAfterVerifyView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request):
        verified = request.session.get("pw_verified") is True
        verified_at = request.session.get("pw_verified_at")

        if not verified or not verified_at:
            messages.warning(request, "먼저 본인 인증을 진행해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        age = timezone.now().timestamp() - float(verified_at)
        if age > 600:
            request.session.pop("pw_verified", None)
            request.session.pop("pw_verified_at", None)
            messages.warning(request, "인증 시간이 만료되었습니다. 다시 본인 인증을 해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        form = SetPasswordForm(user=request.user, data=request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=edit")

        user = form.save()
        update_session_auth_hash(request, user)

        request.session.pop("pw_verified", None)
        request.session.pop("pw_verified_at", None)

        messages.success(request, "비밀번호가 변경되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
@method_decorator(never_cache, name="dispatch")
class PasswordResetSetView(View):
    """
    PW 찾기 2단계: 본인 확인된 상태에서 새 비밀번호 설정
    """

    def post(self, request):
        verified = request.session.get("reset_verified") is True
        verified_at = request.session.get("reset_verified_at")
        reset_user_id = request.session.get("reset_user_id")

        if not verified or not verified_at or not reset_user_id:
            messages.warning(request, "먼저 본인 확인을 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        age = timezone.now().timestamp() - float(verified_at)
        if age > 600:
            request.session.pop("reset_verified", None)
            request.session.pop("reset_verified_at", None)
            request.session.pop("reset_user_id", None)
            messages.warning(request, "인증 시간이 만료되었습니다. 다시 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        user = User.objects.filter(id=reset_user_id).first()
        if not user:
            messages.warning(request, "사용자 정보를 찾을 수 없습니다. 다시 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        form = SetPasswordForm(user=user, data=request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/find/?tab=pw")

        form.save()

        request.session.pop("reset_verified", None)
        request.session.pop("reset_verified_at", None)
        request.session.pop("reset_user_id", None)

        messages.success(request, "비밀번호가 변경되었습니다. 로그인해 주세요.")
        return redirect("/accounts/login/")