"""One transaction for a booking and its inventory; no client-side availability decisions."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from tours.models import Departure, Tour
from .models import Booking


class BookingError(Exception):
    def __init__(self, message, code="unavailable"):
        self.code = code
        super().__init__(message)


@transaction.atomic
def create_booking(*, user, departure_id, seats, request_key):
    if not user.is_authenticated:
        raise BookingError("Войдите в аккаунт, чтобы забронировать места.", "auth")
    if isinstance(seats, bool) or not isinstance(seats, int) or seats <= 0:
        raise BookingError("Укажите целое положительное количество мест.", "quantity")
    # A per-user lock also serializes retries sent to different departure URLs.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    existing = Booking.objects.filter(user=user, request_key=request_key).first()
    if existing:
        if existing.departure_id != departure_id or existing.seats != seats:
            raise BookingError("Этот запрос уже использован для другой брони.", "request")
        return existing
    tour_id = Departure.objects.values_list("tour_id", flat=True).get(pk=departure_id)
    tour = Tour.objects.select_for_update().get(pk=tour_id)
    departure = Departure.objects.select_for_update().get(pk=departure_id)
    if tour.is_archived or departure.status != Departure.Status.OPEN:
        raise BookingError("Бронирование этого выезда закрыто.")
    if departure.starts_at <= timezone.now():
        raise BookingError("Выезд уже начался. Выберите другие даты.", "started")
    if seats > departure.available_seats:
        raise BookingError(f"Недостаточно мест. Сейчас свободно: {departure.available_seats}.", "capacity")
    booking = Booking.objects.create(user=user, departure=departure, seats=seats, unit_price=departure.price, request_key=request_key)
    Departure.objects.filter(pk=departure.pk).update(reserved_seats=F("reserved_seats") + seats)
    return booking


@transaction.atomic
def cancel_booking(*, user, reference):
    if not user.is_authenticated:
        raise BookingError("Войдите в аккаунт.", "auth")
    original = Booking.objects.filter(reference=reference, user=user).first()
    if original is None:
        raise BookingError("Бронь не найдена или принадлежит другому пользователю.", "permission")
    departure = Departure.objects.select_for_update().get(pk=original.departure_id)
    booking = Booking.objects.select_for_update().get(pk=original.pk)
    if booking.status == Booking.Status.CANCELLED:
        return booking
    if departure.starts_at <= timezone.now():
        raise BookingError("Отменить бронь можно только до начала выезда.", "started")
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()
    booking.save(update_fields=["status", "cancelled_at"])
    Departure.objects.filter(pk=departure.pk).update(reserved_seats=F("reserved_seats") - booking.seats)
    return booking
