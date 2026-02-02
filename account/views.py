from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.db import transaction

from shop.models import Account,Transaction  # Account 모델 위치 주의

User = get_user_model()


# ✅ forms.py 대신 views.py 안에 Form 정의
class SignUpForm(UserCreationForm):
    name = forms.CharField(max_length=50, label="이름",help_text="숫자만 입력 (예: 01012345678)")
    phone = forms.CharField(max_length=11, label="전화번호")
    bank_name = forms.CharField(max_length=50, label="은행명")
    account_number = forms.CharField(max_length=50, label="계좌번호")
    balance = forms.DecimalField(max_digits=14, label="현재 잔액")

    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "name",
            "phone",
            "bank_name",
            "account_number",
            "balance"
        )

# ✅ 회원가입 View
class SignUpView(View):
    template_name = "account/signup.html"

    def get(self, request):
        form = SignUpForm()
        return render(request, self.template_name, {"form": form})

    @transaction.atomic
    #부분저장(반쪽 저장) 방지

    def post(self, request):
        form = SignUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = form.save()

        # 회원가입 시 Account 생성
        Account.objects.create(
            user=user,
            name=form.cleaned_data["name"],
            phone = form.cleaned_data["phone"],
            bank_name=form.cleaned_data["bank_name"],
            account_number=form.cleaned_data["account_number"],
            balance=form.cleaned_data["balance"],
            is_active=True,
        )

        login(request, user)
        return redirect("product_list")
    
class MypageView(LoginRequiredMixin, View):
    template_name = "account/mypage.html"
    login_url = "login"
    redirect_field_name = "next"

    def get(self, request):
        account = Account.objects.filter(user=request.user).first()
        return render(request, self.template_name,{"user_obj":request.user,
                                                    "account":account})

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

    

