import uuid
from django.conf import settings
from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Подтверждена"
        CANCELLED = "cancelled", "Отменена"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request_key = models.UUIDField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    departure = models.ForeignKey("tours.Departure", on_delete=models.PROTECT, related_name="bookings")
    seats = models.PositiveIntegerField("Мест")
    unit_price = models.DecimalField("Цена за место при бронировании", max_digits=10, decimal_places=2)
    status = models.CharField("Состояние", max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "бронь"
        verbose_name_plural = "брони"
        constraints = [
            models.UniqueConstraint(fields=["user", "request_key"], name="booking_unique_user_request"),
            models.CheckConstraint(condition=models.Q(seats__gt=0), name="booking_positive_seats"),
            models.CheckConstraint(condition=models.Q(unit_price__gt=0), name="booking_positive_price"),
        ]

    @property
    def code(self):
        return str(self.reference).split("-")[0].upper()

    @property
    def total_price(self):
        return self.unit_price * self.seats

    def __str__(self):
        return f"{self.code} · {self.user} · {self.seats} мест"
