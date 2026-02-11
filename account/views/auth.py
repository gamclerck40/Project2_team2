from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from account.models import Account, Address
from shop.models import Transaction
from account.utils.forms import SignUpForm, FindIDForm, PasswordVerifyForm

User = get_user_model()


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

                account = Account.objects.create(
                    user=user,
                    name=form.cleaned_data["name"],
                    phone=form.cleaned_data["phone"],
                    bank=form.cleaned_data["bank"],
                    account_number=form.cleaned_data["account_number"],
                    balance=form.cleaned_data["balance"],
                    is_active=True,
                    is_default=True,  # ✅ 첫 계좌는 기본 계좌
                )

                # ✅ [핵심] 회원가입 초기 충전도 입금(Transaction)으로 기록
                init_amount = int(form.cleaned_data.get("balance") or 0)
                if init_amount > 0:
                    Transaction.objects.create(
                        user=user,
                        account=account,
                        category=None,
                        product=None,
                        quantity=1,
                        tx_type=Transaction.IN,
                        amount=init_amount,
                        occurred_at=timezone.now(),
                        product_name="회원가입 충전",
                        merchant="내 지갑",
                        memo="회원가입 시 초기 충전",
                    )
                    
                Address.objects.create(
                    user=user,
                    zip_code=form.cleaned_data["zip_code"],
                    address=form.cleaned_data["address"],
                    detail_address=form.cleaned_data["detail_address"],
                    is_default=True,
                )

        except IntegrityError as e:
            form.add_error(None, f"저장 실패: {e}")
            return render(request, self.template_name, {"form": form})

        login(request, user)
        return redirect("product_list")


@method_decorator(never_cache, name="dispatch")
class FindAccountView(View):
    template_name = "account/find_account.html"

    def get(self, request):
        tab = request.GET.get("tab", "id")
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
            if not form.is_valid():
                return render(
                    request,
                    self.template_name,
                    {"tab": "id", "id_form": form, "pw_form": PasswordVerifyForm()},
                )

            phone = form.cleaned_data["phone"]
            users = User.objects.filter(accounts__phone=phone)
            return render(request, "account/find_id_result.html", {"users": users})

        # ✅ PW 찾기(기존 흐름 유지)
        if tab == "pw":
            form = PasswordVerifyForm(request.POST)
            if not form.is_valid():
                messages.warning(request, "비밀번호를 입력해 주세요.")
                return redirect("/accounts/find/?tab=pw")

            pw = form.cleaned_data["current_password"]
            if not request.user.check_password(pw):
                messages.warning(request, "현재 비밀번호가 올바르지 않습니다.")
                return redirect("/accounts/find/?tab=pw")

            request.session["pw_verified"] = True
            request.session["pw_verified_at"] = timezone.now().timestamp()
            return redirect("/accounts/password-reset/set/")
