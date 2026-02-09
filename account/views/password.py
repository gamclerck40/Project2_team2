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


# (로그인 상태에서) '비밀번호 재설정 화면'을 보여주고, 새 비밀번호로 실제 변경까지 수행하는 뷰
@method_decorator(never_cache, name="dispatch")
class PasswordResetView(LoginRequiredMixin, View):
    """
    ✅ 목적: (로그인 상태에서) '비밀번호 재설정 화면'을 보여주고, 새 비밀번호로 실제 변경까지 수행하는 뷰
    - GET: 본인 인증(pw_verified 세션)이 되어있으면 SetPasswordForm 화면 렌더
    - POST: SetPasswordForm 검증 후 비밀번호 변경 저장 + 세션 인증 유지(update_session_auth_hash)
    - 변경이 끝나면 pw_verified 관련 세션 제거 후 로그인 페이지로 이동
    """
    template_name = "account/find_password_reset.html"

    def get(self, request):
        # ✅ pw_verified 세션이 없으면: "먼저 본인 인증" 요구하고 find 페이지로 이동
        if not request.session.get("pw_verified"):
            messages.warning(request, "먼저 본인 인증을 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        # ✅ 본인 인증 완료 상태면: 새 비밀번호 입력 폼 렌더
        form = SetPasswordForm(user=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        # ✅ 새 비밀번호 입력값 검증(SetPasswordForm은 new_password1/2 검증을 포함)
        form = SetPasswordForm(user=request.user, data=request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        # ✅ 비밀번호 저장
        user = form.save()

        # ✅ 비밀번호 변경 후에도 로그인 세션 유지(안하면 로그아웃될 수 있음)
        update_session_auth_hash(request, user)

        # ✅ 본인 인증 플래그 제거(1회 인증 후 재사용 방지)
        request.session.pop("pw_verified", None)
        request.session.pop("pw_verified_at", None)

        messages.success(request, "비밀번호가 변경되었습니다.")
        return redirect("login")


@method_decorator(never_cache, name="dispatch")
class PasswordResetVerifyView(View):
    """
    ✅ 목적: (로그인/비로그인 모두 가능하게 설계된 것으로 보임) '비밀번호 찾기' 흐름에서 본인확인을 수행하는 뷰
    - POST만 지원
    - PasswordResetVerifyForm으로 사용자를 검증(예: 아이디/이메일/휴대폰 등)
    - 성공 시 reset_verified/reset_verified_at/reset_user_id를 세션에 저장하여
      다음 단계(PasswordResetSetView)가 "인증 완료된 사용자"에 대해서만 비번 변경을 허용하게 함
    """
    def post(self, request):
        form = PasswordResetVerifyForm(request.POST)

        # ✅ 본인확인 실패: 폼 에러 메시지를 messages로 띄우고 find 페이지로 복귀
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/find/?tab=pw")

        # ✅ 본인확인 성공: 세션에 인증정보 저장(시간 제한 처리용 timestamp 포함)
        request.session["reset_verified"] = True
        request.session["reset_verified_at"] = timezone.now().timestamp()
        request.session["reset_user_id"] = form.user.id

        messages.success(request, "본인 확인이 완료되었습니다. 새 비밀번호를 설정해 주세요.")
        return redirect("/accounts/find/?tab=pw")

# '비밀번호 찾기' 흐름에서, 본인확인이 끝난 사용자(reset_verified 세션)에 한해 새 비밀번호를 저장하는 뷰 (비로그인 사용자도 가능하도록 설계)
@method_decorator(never_cache, name="dispatch")
class PasswordResetSetView(View):
    """
    ✅ 목적: '비밀번호 찾기' 흐름에서, 본인확인이 끝난 사용자(reset_verified 세션)에 한해
            새 비밀번호를 저장하는 뷰 (비로그인 사용자도 가능하도록 설계)
    - POST만 지원
    - 세션(reset_verified/reset_verified_at/reset_user_id) 검증
    - 인증 유효시간(10분=600초) 체크
    - SetPasswordForm으로 비밀번호 저장
    - 성공 시 세션 정리 후 로그인 페이지로 이동
    """
    def post(self, request):
        verified = request.session.get("reset_verified") is True
        verified_at = request.session.get("reset_verified_at")
        reset_user_id = request.session.get("reset_user_id")

        # ✅ 인증 세션이 없으면: 먼저 본인확인 요구
        if not verified or not verified_at or not reset_user_id:
            messages.warning(request, "먼저 본인 확인을 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        # ✅ 인증 유효시간 10분 제한
        age = timezone.now().timestamp() - float(verified_at)
        if age > 600:
            request.session.pop("reset_verified", None)
            request.session.pop("reset_verified_at", None)
            request.session.pop("reset_user_id", None)
            messages.warning(request, "인증 시간이 만료되었습니다. 다시 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        # ✅ 세션에 저장된 사용자 id로 대상 사용자 조회
        user = User.objects.filter(id=reset_user_id).first()
        if not user:
            messages.warning(request, "사용자 정보를 찾을 수 없습니다. 다시 진행해 주세요.")
            return redirect("/accounts/find/?tab=pw")

        # ✅ 새 비밀번호 검증 및 저장
        form = SetPasswordForm(user=user, data=request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/find/?tab=pw")

        form.save()

        # ✅ 인증 세션 정리(재사용 방지)
        request.session.pop("reset_verified", None)
        request.session.pop("reset_verified_at", None)
        request.session.pop("reset_user_id", None)

        messages.success(request, "비밀번호가 변경되었습니다. 로그인해 주세요.")
        return redirect("/accounts/login/")

# 마이페이지 내) '비밀번호 변경' 전에 현재 비밀번호를 확인(본인 인증)하는 뷰
@method_decorator(never_cache, name="dispatch")
class PasswordVerifyView(LoginRequiredMixin, View):
    """
    ✅ 목적: (마이페이지 내) '비밀번호 변경' 전에 현재 비밀번호를 확인(본인 인증)하는 뷰
    - POST만 지원
    - PasswordVerifyForm으로 current_password 입력 검증
    - 실제 사용자 비밀번호와 일치하면 pw_verified/pw_verified_at 세션을 저장
    - 이후 PasswordChangeAfterVerifyView에서 이 세션을 확인하고 새 비밀번호 변경을 허용
    """
    login_url = "login"

    def post(self, request):
        # ✅ 현재 비밀번호 입력 폼 검증(빈 값 등)
        form = PasswordVerifyForm(request.POST)
        if not form.is_valid():
            messages.warning(request, "비밀번호를 입력해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        pw = form.cleaned_data["current_password"]

        # ✅ 입력한 비밀번호가 실제 계정 비밀번호와 불일치
        if not request.user.check_password(pw):
            messages.warning(request, "현재 비밀번호가 올바르지 않습니다.")
            return redirect("/accounts/mypage/?tab=edit")

        # ✅ 일치하면 "본인 인증 완료" 세션 플래그 저장 (유효시간 체크용 timestamp 포함)
        request.session["pw_verified"] = True
        request.session["pw_verified_at"] = timezone.now().timestamp()

        messages.success(request, "본인 인증이 완료되었습니다. 새 비밀번호를 설정해 주세요.")
        return redirect("/accounts/mypage/?tab=edit")


@method_decorator(never_cache, name="dispatch")
class PasswordChangeAfterVerifyView(LoginRequiredMixin, View):
    """
    ✅ 목적: PasswordVerifyView에서 본인 인증(pw_verified 세션)을 완료한 사용자에 한해
            마이페이지에서 새 비밀번호를 실제로 변경하는 뷰
    - POST만 지원
    - pw_verified/pw_verified_at 세션 검증 + 유효시간 10분 제한
    - SetPasswordForm으로 새 비밀번호 저장
    - Account.updated_at 갱신(계좌 정보 UI에 Updated 표시용으로 보임)
    - update_session_auth_hash로 비밀번호 변경 후 로그인 세션 유지
    - 성공 후 pw_verified 세션 제거 + 프로필 탭으로 이동
    """
    login_url = "login"

    def post(self, request):
        verified = request.session.get("pw_verified") is True
        verified_at = request.session.get("pw_verified_at")

        # ✅ 본인 인증 세션 없으면: 먼저 인증 요구
        if not verified or not verified_at:
            messages.warning(request, "먼저 본인 인증을 진행해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        # ✅ 인증 유효시간 10분 제한
        age = timezone.now().timestamp() - float(verified_at)
        if age > 600:
            request.session.pop("pw_verified", None)
            request.session.pop("pw_verified_at", None)
            messages.warning(request, "인증 시간이 만료되었습니다. 다시 본인 인증을 해 주세요.")
            return redirect("/accounts/mypage/?tab=edit")

        # ✅ 새 비밀번호 검증 및 저장
        form = SetPasswordForm(user=request.user, data=request.POST)
        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.warning(request, e)
            return redirect("/accounts/mypage/?tab=edit")

        user = form.save()

        # ✅ 계좌(updated_at)를 갱신해 "내 정보" 페이지에 표시되는 Updated 시간을 최신화하려는 의도
        Account.objects.filter(user=request.user).update(updated_at=timezone.now())

        # ✅ 비밀번호 변경 후에도 로그인 세션 유지
        update_session_auth_hash(request, user)

        # ✅ 인증 세션 제거(재사용 방지)
        request.session.pop("pw_verified", None)
        request.session.pop("pw_verified_at", None)

        messages.success(request, "비밀번호가 변경되었습니다.")
        return redirect("/accounts/mypage/?tab=profile")
