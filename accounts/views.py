from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import LoginForm, RegistrationForm


def safe_next(request):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
        return target
    return "tours:home"


def register(request):
    if request.user.is_authenticated:
        return redirect("tours:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Аккаунт создан. Ваше путешествие начинается!")
        return redirect(safe_next(request))
    return render(request, "accounts/auth.html", {"form": form, "register": True, "next": request.GET.get("next", "")})


class SignInView(LoginView):
    template_name = "accounts/auth.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
