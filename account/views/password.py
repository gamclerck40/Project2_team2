from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from account.utils.forms import PasswordResetVerifyForm, PasswordVerifyForm
from account.models import Account 
User = get_user_model()


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
    def post(self, request):
        form = PasswordResetVerifyForm(request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/find/?tab=pw")

        request.session["reset_verified"] = True
        request.session["reset_verified_at"] = timezone.now().timestamp()
        request.session["reset_user_id"] = form.user.id

        messages.success(request, "본인 확인이 완료되었습니다. 새 비밀번호를 설정해 주세요.")
        return redirect("/accounts/find/?tab=pw")


@method_decorator(never_cache, name="dispatch")
class PasswordResetSetView(View):
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
        Account.objects.filter(user=request.user).update(updated_at=timezone.now())
        update_session_auth_hash(request, user)

        request.session.pop("pw_verified", None)
        request.session.pop("pw_verified_at", None)

        messages.success(request, "비밀번호가 변경되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
