from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)
        labels = {"username": "Логин"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(placeholder="Например, anna_travel", autocomplete="username")
        self.fields["password1"].widget.attrs.update(placeholder="Не менее 8 символов", autocomplete="new-password")
        self.fields["password2"].widget.attrs.update(placeholder="Повторите пароль", autocomplete="new-password")


class LoginForm(AuthenticationForm):
    error_messages = {"invalid_login": "Неверный логин или пароль", "inactive": "Неверный логин или пароль"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(placeholder="Ваш логин", autocomplete="username")
        self.fields["password"].widget.attrs.update(placeholder="Ваш пароль", autocomplete="current-password")
