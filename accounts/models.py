from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    @property
    def display_name(self):
        return self.first_name or self.username
