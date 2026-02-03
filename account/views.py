import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from shop.models import Account,Transaction, Bank  # Account 모델 위치 주의
from django.contrib import messages
from django.utils import timezone

User = get_user_model()


# ✅ forms.py 대신 views.py 안에 Form 정의
class SignUpForm(UserCreationForm):
    name = forms.CharField(max_length=50, label="이름")
    phone = forms.CharField(max_length=11, label="전화번호",help_text="숫자만 입력 (예: 01012345678)")
    bank = forms.ModelChoiceField(queryset=Bank.objects.all(), empty_label="은행 선택")    
    account_number = forms.CharField(max_length=50, label="계좌번호")
    balance = forms.DecimalField(max_digits=14, label="현재 잔액")

    #'Meta' 클래스는 아래 폼을 기반으로 이 필드들을 화면에 보여주고 처리함을 선언.
    # Meta는 하드코딩으로 찾는 약속된 이름 -> 임의 변경 X
    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "name",
            "phone",
            "bank",
            "account_number",
            "balance"
        )
    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        phone = re.sub(r"[^0-9]", "", phone)  # 숫자만 남김 (하이픈/공백 제거)

        if not re.match(r"^010\d{7,8}$", phone):
            raise ValidationError("전화번호 형식이 올바르지 않습니다. (예: 01012345678)")

        if Account.objects.filter(phone=phone).exists():
            raise ValidationError("이미 사용 중인 전화번호입니다.")

        return phone

# ✅ 회원가입 View -> SignUpForm을 가져와서 signup.html로 데이터 보내기.
# POST 방식으로 보냄.
class SignUpView(View):
    template_name = "account/signup.html"

    def get(self, request):
        form = SignUpForm()
        return render(request, self.template_name, {"form": form})
    #부분저장(반쪽 저장) 방지
    def post(self, request):
        form = SignUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        try:
            with transaction.atomic():
                user = form.save()
            # 회원가입 시 Account 생성
                Account.objects.create(
                user=user,
                name=form.cleaned_data["name"],
                phone = form.cleaned_data["phone"],
                bank=form.cleaned_data["bank"],
                account_number=form.cleaned_data["account_number"],
                balance=form.cleaned_data["balance"],
                is_active=True,
            )
        except IntegrityError:
            # 보통 phone unique 때문에 여기로 들어옴
            form.add_error("phone", "이미 사용 중인 전화번호입니다.")
            # 또는 form.add_error(None, "이미 사용 중인 정보가 있습니다.")
            return render(request, self.template_name, {"form": form})

        login(request, user)
        return redirect("product_list")
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
        def format_masking_acc_number(account_number: str) -> str:
            if not account_number:
                return "계좌 정보가 없습니다"
            
        def format_korean_phone(phone: str) -> str:
            if not phone:
                return ""
            digits = re.sub(r"[^0-9]", "", phone)

            # 010 + 7자리: 010-xxx-xxxx
            if re.match(r"^010\d{7}$", digits):
                return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            # 010 + 8자리: 010-xxxx-xxxx
            if re.match(r"^010\d{8}$", digits):
                return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            # 그 외는 원본(혹은 digits) 그대로 반환
            return digits 
        
        account = Account.objects.filter(user=request.user).first()

        formatted_phone = ""
        if account:
            formatted_phone = format_korean_phone(account.phone)
        return render(request, self.template_name,{"user_obj":request.user,
                                                    "account":account,
                                                    "formatted_phone":formatted_phone,
                                                    "receipts":[],
                                                    "pw_verified":pw_verified,
                                                    "banks":Bank.objects.all().order_by("name")},
                                                    )

class FindIDForm(forms.Form):
    phone = forms.CharField(
        label="휴대폰 번호",
        max_length=11,
        widget=forms.TextInput(attrs={
            "placeholder": "01012345678"
        })
    )
class FindIDView(View):
    template_name = "account/find_id.html"

    def get(self, request):
        form = FindIDForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = FindIDForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        phone = form.cleaned_data["phone"]

        # phone이 Account에 있는 경우 (권장 구조)
        users = User.objects.filter(accounts__phone=phone)

        return render(
            request,
            "account/find_id_result.html",
            {"users": users}
        )
class MypageUpdateForm(forms.Form):
    phone = forms.CharField(max_length=11, required=False, label="전화번호")
    bank_name = forms.CharField(max_length=50, required=False, label="은행명")
    account_number = forms.CharField(max_length=50, required=False, label="계좌번호")

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "") or ""
        phone = re.sub(r"[^0-9]", "", phone)

        # 비워도 허용(원하면 required=True로 바꾸면 됨)
        if phone == "":
            return phone

        if not re.match(r"^010\d{7,8}$", phone):
            raise ValidationError("전화번호 형식이 올바르지 않습니다. (예: 01012345678)")
        return phone

    def clean_account_number(self):
        acc = (self.cleaned_data.get("account_number") or "").strip()
        return acc   
class MypageUpdateView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request):
        form = MypageUpdateForm(request.POST)

        if not form.is_valid():
            # 폼 에러를 messages로 보여주고 마이페이지로 복귀
            # (네 프로젝트는 messages를 base.html에서 출력하고 있었음)
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=edit")

        # 유저의 계좌 1개를 수정 대상으로 삼음 (너 기존 MypageView가 first() 쓰는 구조였음)
        account = Account.objects.filter(user=request.user).first()
        if not account:
            messages.warning(request, "수정할 계좌 정보가 없습니다. 먼저 계좌를 등록하세요.")
            return redirect("/accounts/mypage/?tab=profile")

        phone = form.cleaned_data["phone"]
        bank_name = form.cleaned_data["bank_name"]
        account_number = form.cleaned_data["account_number"]

        try:
            with transaction.atomic():
                # 비어있지 않으면 업데이트
                if phone != "":
                    account.phone = phone
                if bank_name != "":
                    account.bank_name = bank_name
                if account_number != "":
                    account.account_number = account_number

                account.save()

        except IntegrityError:
            # account_number unique constraint(예: 유저별/전역) 등에 걸릴 때 주로 발생
            messages.warning(request, "이미 사용 중인 계좌번호이거나 저장할 수 없는 값입니다.")
            return redirect("/accounts/mypage/?tab=edit")

        messages.success(request, "내 정보가 수정되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
class PasswordVerifyForm(forms.Form):
    current_password = forms.CharField(
        label="현재 비밀번호",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )

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

        # ✅ 인증 성공: 세션에 인증 플래그 + 시간 기록
        request.session["pw_verified"] = True
        request.session["pw_verified_at"] = timezone.now().timestamp()

        messages.success(request, "본인 인증이 완료되었습니다. 새 비밀번호를 설정해 주세요.")
        return redirect("/accounts/mypage/?tab=edit")


class PasswordChangeAfterVerifyView(LoginRequiredMixin, View):
    login_url = "login"

    def post(self, request):
        # ✅ 세션 인증 확인(예: 10분 유효)
        verified = request.session.get("pw_verified") is True
        verified_at = request.session.get("pw_verified_at")

        if not verified or not verified_at:
            messages.warning(request, "먼저 본인 인증을 진행해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        # 10분 제한(원하면 변경 가능)
        age = timezone.now().timestamp() - float(verified_at)
        if age > 600:
            request.session.pop("pw_verified", None)
            request.session.pop("pw_verified_at", None)
            messages.warning(request, "인증 시간이 만료되었습니다. 다시 본인 인증을 해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        form = SetPasswordForm(user=request.user, data=request.POST)
        if not form.is_valid():
            # 폼 에러 messages로 표시
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=edit")

        user = form.save()  # ✅ 실제 비밀번호 변경
        update_session_auth_hash(request, user)  # ✅ 로그인 유지(안 하면 로그아웃됨)

        # ✅ 인증 플래그 제거
        request.session.pop("pw_verified", None)
        request.session.pop("pw_verified_at", None)

        messages.success(request, "비밀번호가 변경되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")