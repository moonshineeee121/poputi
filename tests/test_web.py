from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingError, cancel_booking, create_booking
from tours.models import Departure, Tour

pytestmark = pytest.mark.django_db


@pytest.fixture
def traveler():
    return get_user_model().objects.create_user(username="traveler", password="Travel2027!")


@pytest.fixture
def trip(traveler):
    owner = get_user_model().objects.create_user(username="guide")
    tour = Tour.objects.create(organizer=owner, name="Алтай", slug="altai", direction="Республика Алтай", category="hiking", program="Маршрут к озеру")
    start = timezone.now() + timedelta(days=30)
    return Departure.objects.create(tour=tour, starts_at=start, ends_at=start + timedelta(days=5), price=Decimal("20000"), capacity=6)


def book(user, trip, seats=2, key=None):
    return create_booking(user=user, departure_id=trip.pk, seats=seats, request_key=key or uuid4())


def test_home_renders_real_catalog(client, trip):
    response = client.get(reverse("tours:home"))
    assert response.status_code == 200
    assert len(response.context["cards"]) == 1
    assert response.context["cards"][0]["tour"].pk == trip.tour_id
    assert "Мир ближе" in response.content.decode()


def test_search_combines_unicode_text_category_and_inclusive_price(client, trip):
    response = client.get(reverse("tours:home"), {"q": "  аЛтАй  ", "category": "hiking", "price_from": "20000", "price_to": "20000"})
    assert [card["tour"].pk for card in response.context["cards"]] == [trip.tour_id]
    response = client.get(reverse("tours:home"), {"q": "Алтай", "category": "excursion"})
    assert response.context["cards"] == []


def test_invalid_filter_does_not_silently_show_results(client, trip):
    response = client.get(reverse("tours:home"), {"price_from": 30000, "price_to": 10000})
    assert response.context["search"].errors
    assert response.context["cards"] == []


def test_archived_and_started_departures_are_not_search_results(client, trip):
    Departure.objects.filter(pk=trip.pk).update(starts_at=timezone.now() - timedelta(days=1))
    assert client.get(reverse("tours:home"), {"q": "Алтай"}).context["cards"] == []
    trip.tour.is_archived = True
    trip.tour.save()
    assert client.get(trip.tour.get_absolute_url()).status_code == 404


def test_tour_without_departures_still_has_public_description(client, trip):
    Departure.objects.filter(pk=trip.pk).update(status="closed")
    response = client.get(reverse("tours:home"))
    assert response.context["cards"][0]["departure"] is None
    assert client.get(trip.tour.get_absolute_url()).status_code == 200


def test_browser_booking_and_cancellation_flow(client, traveler, trip):
    assert client.post(reverse("accounts:login"), {"username": traveler.username, "password": "Travel2027!"}).status_code == 302
    key = str(uuid4())
    response = client.post(reverse("bookings:create", args=[trip.pk]), {"seats": 2, "request_key": key}, follow=True)
    assert response.status_code == 200 and response.resolver_match.view_name == "bookings:mine"
    booking = Booking.objects.get(user=traveler)
    assert booking.code in response.content.decode()
    trip.refresh_from_db()
    assert trip.available_seats == 4
    response = client.post(reverse("bookings:cancel", args=[booking.reference]), follow=True)
    assert response.status_code == 200 and "Отменена" in response.content.decode()
    trip.refresh_from_db()
    assert trip.available_seats == 6


def test_stale_page_cannot_overbook_via_http(client, traveler, trip):
    client.force_login(traveler)
    book(traveler, trip, 5)
    response = client.post(reverse("bookings:create", args=[trip.pk]), {"seats": 2, "request_key": uuid4()})
    assert response.status_code == 400
    assert "Недостаточно мест" in response.content.decode()
    assert Booking.objects.count() == 1


def test_http_retry_keeps_one_booking(client, traveler, trip):
    client.force_login(traveler)
    payload = {"seats": 2, "request_key": str(uuid4())}
    url = reverse("bookings:create", args=[trip.pk])
    assert client.post(url, payload).status_code == 302
    assert client.post(url, payload).status_code == 302
    assert Booking.objects.count() == 1
    trip.refresh_from_db()
    assert trip.available_seats == 4


def test_foreign_booking_is_hidden_and_cannot_be_cancelled(client, traveler, trip):
    booking = book(traveler, trip)
    stranger = get_user_model().objects.create_user(username="stranger")
    client.force_login(stranger)
    response = client.get(reverse("bookings:mine"))
    assert booking.code not in response.content.decode()
    assert client.post(reverse("bookings:cancel", args=[booking.reference])).status_code == 404
    booking.refresh_from_db()
    assert booking.status == "confirmed"


def test_client_cannot_set_booking_price(client, traveler, trip):
    client.force_login(traveler)
    response = client.post(reverse("bookings:create", args=[trip.pk]), {"seats": 2, "request_key": uuid4(), "unit_price": "1"})
    assert response.status_code == 302
    assert Booking.objects.get().total_price == Decimal("40000")


def test_reusing_request_for_different_quantity_is_rejected(traveler, trip):
    key = uuid4()
    book(traveler, trip, 2, key)
    with pytest.raises(BookingError) as error:
        book(traveler, trip, 3, key)
    assert error.value.code == "request"
    assert Booking.objects.count() == 1


def test_departure_changes_preserve_current_inventory(traveler, trip):
    # This instance was fetched before the booking changed the inventory.
    book(traveler, trip, 4)
    trip.capacity = 8
    trip.save()
    trip.refresh_from_db()
    assert trip.reserved_seats == 4 and trip.available_seats == 4
    trip.capacity = 3
    with pytest.raises(ValidationError):
        trip.save()
    assert Departure.objects.get(pk=trip.pk).capacity == 8


def test_dates_and_price_remain_fixed_after_cancelled_booking(traveler, trip):
    booking = book(traveler, trip)
    cancel_booking(user=traveler, reference=booking.reference)
    trip.price = Decimal("25000")
    with pytest.raises(ValidationError):
        trip.save()
    assert Departure.objects.get(pk=trip.pk).price == Decimal("20000")


def test_database_constraint_rejects_overfilled_inventory(trip):
    with pytest.raises(IntegrityError), transaction.atomic():
        Departure.objects.filter(pk=trip.pk).update(reserved_seats=7)


def test_csrf_is_required_for_registration():
    browser = Client(enforce_csrf_checks=True)
    response = browser.post(reverse("accounts:register"), {"username": "new_traveler", "password1": "Travel2027!", "password2": "Travel2027!"})
    assert response.status_code == 403
    assert not get_user_model().objects.filter(username="new_traveler").exists()


def test_registration_does_not_redirect_to_external_site(client):
    response = client.post(reverse("accounts:register"), {"username": "new_traveler", "password1": "Travel2027!", "password2": "Travel2027!", "next": "https://untrusted.example/"})
    assert response.status_code == 302 and response.url == reverse("tours:home")
    assert "_auth_user_id" in client.session


def test_logout_requires_post(client, traveler):
    client.force_login(traveler)
    assert client.get(reverse("accounts:logout")).status_code == 405
    assert "_auth_user_id" in client.session
