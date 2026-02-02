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
    name = forms.CharField(max_length=50, label="이름")
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
    def post(self, request):
        form = SignUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = form.save()

        # 회원가입 시 Account 생성
        Account.objects.create(
            user=user,
            name=form.cleaned_data["name"],
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
