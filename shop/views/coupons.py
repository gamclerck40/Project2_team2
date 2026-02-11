from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from shop.models import Coupon, UserCoupon


class CouponRegisterView(LoginRequiredMixin, View):
    """
    CBV 방식의 쿠폰 등록 및 목록 조회 뷰
    """
    def get(self, request):
        # 유저가 보유한 쿠폰 목록을 최신순으로 가져옴
        user_coupons = UserCoupon.objects.filter(user=request.user).order_by('-issued_at')
        return render(request, 'shop/register_coupon.html', {
            'user_coupons': user_coupons
        })

    def post(self, request):
        code = request.POST.get('coupon_code', '').strip().upper()

        # 1. 존재 여부 확인
        coupon = Coupon.objects.filter(code=code, active=True).first()

        if not coupon:
            messages.error(request, "유효하지 않거나 사용 중지된 쿠폰 코드입니다.")
        # 2. 유효 기간 확인
        elif coupon.valid_to < timezone.now():
            messages.error(request, "사용 기간이 만료된 쿠폰입니다.")
        # 3. 중복 발급 확인
        elif UserCoupon.objects.filter(user=request.user, coupon=coupon).exists():
            messages.warning(request, "이미 등록된 쿠폰입니다.")
        else:
            # 4. 발급 처리
            UserCoupon.objects.create(user=request.user, coupon=coupon)
            messages.success(request, f"🎉 [{coupon.name}] 쿠폰이 성공적으로 등록되었습니다!")

        return redirect('register_coupon')