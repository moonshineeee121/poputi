from django.urls import path
from . import views

app_name = "tours"
urlpatterns = [path("", views.home, name="home"), path("tours/<slug:slug>/", views.detail, name="detail")]
