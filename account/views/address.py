from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from shop.models import *
from account.models import *


@method_decorator(never_cache, name="dispatch")
class AddressDeleteView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = Address.objects.filter(id=address_id, user=request.user).first()
        if address and not address.is_default:
            address.delete()
            messages.success(request, "배송지가 삭제되었습니다.")
        else:
            messages.warning(request, "기본 배송지는 삭제할 수 없습니다.")
        return redirect("/accounts/mypage/?tab=profile")

class SetDefaultAddressView(LoginRequiredMixin, View):
    def post(self, request):
        # 1. 프로필 탭의 라디오 버튼(name="default_addr_id")에서 선택된 ID 가져오기
        selected_addr_id = request.POST.get("default_addr_id")
        
        if selected_addr_id:
            # 2. 로그인한 유저의 모든 주소를 False로 초기화
            Address.objects.filter(user=request.user).update(is_default=False)
            
            # 3. 사용자가 선택한 주소만 True로 변경
            Address.objects.filter(id=selected_addr_id, user=request.user).update(is_default=True)
            
        return redirect("mypage")
