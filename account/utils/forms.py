import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError

from account.models import Account, Bank

User = get_user_model()


# 회원가입 페이지 Form
class SignUpForm(UserCreationForm):
    name = forms.CharField(max_length=50, label="이름")
    phone = forms.CharField(
        max_length=11, label="전화번호", help_text="숫자만 입력 (예: 01012345678)"
    )
    bank = forms.ModelChoiceField(queryset=Bank.objects.all())
    account_number = forms.CharField()
    balance = forms.DecimalField(max_digits=14, label="현재 잔액")
    zip_code = forms.CharField(
        max_length=10,
        label="우편번호",
        widget=forms.TextInput(
            attrs={
                "style": "width:100%; border:none; outline:none;",
                "placeholder": "예) 12345",
            }
        ),
    )
    address = forms.CharField(
        max_length=255,
        label="기본 주소",
        widget=forms.TextInput(
            attrs={
                "style": "width:100%; border:none; outline:none;",
                "placeholder": "시/도 구/군 도로명",
            }
        ),
    )
    detail_address = forms.CharField(
        max_length=255,
        label="상세 주소",
        widget=forms.TextInput(
            attrs={
                "style": "width:100%; border:none; outline:none;",
                "placeholder": "동/호수 등 상세정보",
            }
        ),
    )

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
            "balance",
            "zip_code",
            "address",
            "detail_address",
        )

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "") or ""
        phone = re.sub(r"[^0-9]", "", phone)

        if not re.match(r"^010\d{7,8}$", phone):
            raise ValidationError(
                "전화번호 형식이 올바르지 않습니다. (예: 01012345678)"
            )

        if Account.objects.filter(phone=phone).exists():
            raise ValidationError("이미 사용 중인 전화번호입니다.")

        return phone
    def clean_bank(self):
        bank = self.cleaned_data.get("bank")
        if not bank:
            raise ValidationError("은행을 선택해 주세요.")
        return bank
    
    def clean_account_num(self):
        cleaned = super().clean()
        bank = cleaned.get("bank")
        acc_raw = cleaned.get("account_number") or ""
        acc = re.sub(r"[^0-9]", "", acc_raw)

        if not bank:
            return cleaned

        # ✅ 길이 검증
        if bank.min_len and len(acc) < bank.min_len:
            raise ValidationError({"account_number": f"{bank.name} 계좌번호는 최소 {bank.min_len}자리입니다."})
        if bank.max_len and len(acc) > bank.max_len:
            raise ValidationError({"account_number": f"{bank.name} 계좌번호는 최대 {bank.max_len}자리입니다."})

        # ✅ 접두(prefix) 검증
        prefixes = bank.prefixes()
        if prefixes and not any(acc.startswith(p) for p in prefixes):
            raise ValidationError({"account_number": f"{bank.name} 계좌번호 형식(접두)이 올바르지 않습니다."})

        # ✅ 전역 중복 검증(타인 포함)
        if Account.objects.filter(bank=bank, account_number=acc).exists():
            raise ValidationError({"account_number": "이미 등록된 계좌입니다. 다른 사용자가 사용 중입니다."})

        cleaned["account_number"] = acc
        return cleaned
    
class AccountAddForm(forms.Form):
    bank = forms.ModelChoiceField(
        queryset=Bank.objects.all().order_by("name"),
        empty_label="은행 선택",
        label="은행",
    )
    account_number = forms.CharField(max_length=50, label="계좌번호")

    def clean(self):
        cleaned = super().clean()
        bank = cleaned.get("bank")
        acc_raw = cleaned.get("account_number") or ""
        acc = re.sub(r"[^0-9]", "", acc_raw)

        if not bank:
            return cleaned

        if bank.min_len and len(acc) < bank.min_len:
            raise ValidationError({"account_number": f"{bank.name} 계좌번호는 최소 {bank.min_len}자리입니다."})
        if bank.max_len and len(acc) > bank.max_len:
            raise ValidationError({"account_number": f"{bank.name} 계좌번호는 최대 {bank.max_len}자리입니다."})

        prefixes = bank.prefixes()
        if prefixes and not any(acc.startswith(p) for p in prefixes):
            raise ValidationError({"account_number": f"{bank.name} 계좌번호 형식(접두)이 올바르지 않습니다."})

        # 전역 중복
        if Account.objects.filter(bank=bank, account_number=acc).exists():
            raise ValidationError({"account_number": "이미 등록된 계좌입니다."})

        cleaned["account_number"] = acc
        return cleaned

# ID 찾기 UI
class FindIDForm(forms.Form):
    phone = forms.CharField(
        label="휴대폰 번호",
        max_length=11,
        widget=forms.TextInput(attrs={"placeholder": "01012345678"}),
    )

# 내 정보 수정 Form
class MypageUpdateForm(forms.Form):
    phone = forms.CharField(max_length=11, required=False, label="전화번호")
    bank = forms.ModelChoiceField(
        queryset=Bank.objects.all().order_by("name"),
        required=False,
        empty_label="은행 선택",
        label="은행",
    )
    account_number = forms.CharField(max_length=50, required=False, label="계좌번호")
    zip_code = forms.CharField(max_length=10, required=False)
    address = forms.CharField(max_length=255, required=False)
    detail_address = forms.CharField(max_length=255, required=False)

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "") or ""
        phone = re.sub(r"[^0-9]", "", phone)

        if phone == "":
            return phone

        if not re.match(r"^010\d{7,8}$", phone):
            raise ValidationError(
                "전화번호 형식이 올바르지 않습니다. (예: 01012345678)"
            )
        return phone

    def clean_account_number(self):
        acc = (self.cleaned_data.get("account_number") or "").strip()
        return acc


class PasswordVerifyForm(forms.Form):
    current_password = forms.CharField(
        label="현재 비밀번호",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class PasswordResetVerifyForm(forms.Form):
    username = forms.CharField(label="아이디")
    name = forms.CharField(label="이름")
    account_number = forms.CharField(label="계좌번호")

    def clean_account_number(self):
        acc = (self.cleaned_data.get("account_number") or "").strip()
        acc = re.sub(r"[^0-9]", "", acc)  # 숫자만
        if not acc:
            raise ValidationError("계좌번호를 입력해 주세요.")
        return acc

    def clean(self):
        cleaned = super().clean()
        username = (cleaned.get("username") or "").strip()
        name = (cleaned.get("name") or "").strip()
        acc = cleaned.get("account_number")

        if not username or not name or not acc:
            return cleaned

        # ✅ 사용자 존재 확인
        user = User.objects.filter(username=username).first()
        if not user:
            raise ValidationError("입력한 정보와 일치하는 사용자를 찾을 수 없습니다.")

        # ✅ 계좌(Account) 정보로 본인확인 (user + name + account_number)
        ok = Account.objects.filter(user=user, name=name, account_number=acc).exists()
        if not ok:
            raise ValidationError("입력한 정보가 일치하지 않습니다.")

        # 뷰에서 쓰기 위해 저장
        self.user = user
        return cleaned
