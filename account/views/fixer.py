# account/views/csrf_failure.py
from django.shortcuts import render

def csrf_failure(request, reason=""):
    # reason에는 CSRF 실패 사유가 들어옴
    return render(request, "account/csrf_failure.html", {"reason": reason}, status=403)
