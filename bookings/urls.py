from django.urls import path
from . import views

app_name = "bookings"
urlpatterns = [
    path("", views.mine, name="mine"),
    path("create/<int:departure_id>/", views.create, name="create"),
    path("<uuid:reference>/cancel/", views.cancel, name="cancel"),
]
