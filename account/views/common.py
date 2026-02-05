from django.shortcuts import render


def csrf_failure(request, reason=""):
    return render(request, "errors/csrf_403.html", status=403)