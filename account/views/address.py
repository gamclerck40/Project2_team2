from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from account.models import Address



@method_decorator(never_cache, name="dispatch")
class AddressDeleteView(LoginRequiredMixin, View):
    def post(self, request, address_id):
        address = Address.objects.filter(id=address_id, user=request.user).first()
        if address:
            print(f"삭제 시도 ID: {address.id}, 기본여부: {address.is_default}") # 터미널 확인용

            if not address.is_default:
                address.delete()
                messages.success(request, "배송지가 삭제되었습니다.")
            else:
                messages.warning(request, "기본 배송지는 삭제할 수 없습니다.")
        else:
            messages.error(request, "존재하지 않는 배송지입니다.")        
        return redirect("/accounts/mypage/?tab=profile")

class SetDefaultAddressView(LoginRequiredMixin, View):
    def post(self, request):
        # 프로필 탭의 라디오 버튼(name="default_addr_id")에서 선택된 ID 가져오기
        selected_addr_id = request.POST.get("default_addr_id")
        
        if selected_addr_id:
            # 트랜잭션을 사용해 '전체 False -> 하나 True'가 한 세트로 묶이게 합니다.
            with transaction.atomic():
                # 내 주소 전부 False
                Address.objects.filter(user=request.user).update(is_default=False)
                # 선택한 놈만 True
                Address.objects.filter(id=selected_addr_id, user=request.user).update(is_default=True)
        # 탭 위치를 유지하기 위해 경로 수정
        return redirect("/accounts/mypage/?tab=profile")