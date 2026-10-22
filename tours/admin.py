from django.contrib import admin
from .models import Departure, Tour


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ("name", "organizer", "direction", "is_archived")
    list_filter = ("is_archived", "category")
    prepopulated_fields = {"slug": ("name",)}

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Departure)
class DepartureAdmin(admin.ModelAdmin):
    list_display = ("tour", "starts_at", "price", "capacity", "reserved_seats", "status")
    readonly_fields = ("reserved_seats",)
    list_filter = ("status", "tour")

    def has_delete_permission(self, request, obj=None):
        return False
