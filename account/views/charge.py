from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import View


class AccountChargeView(LoginRequiredMixin, View):
    def get(self, request):
        
        return HttpResponse("충전 페이지 준비중입니다 🙂")