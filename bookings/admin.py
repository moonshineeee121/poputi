from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("code", "user", "departure", "seats", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in Booking._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
