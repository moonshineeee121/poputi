"""Executable steps for the existing account, booking and cancellation specifications."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connections
from django.db.models import F, Sum
from django.urls import reverse
from django.utils import timezone
from pytest_bdd import given, parsers, scenarios, then, when

from bookings.models import Booking
from bookings.services import BookingError, cancel_booking, create_booking
from tours.models import Departure, Tour

pytestmark = pytest.mark.django_db(transaction=True)
scenarios("accounts/registration.feature", "accounts/authentication.feature", "bookings/create_booking.feature", "bookings/cancel_booking.feature")


@pytest.fixture
def state(monkeypatch):
    value = {"now": datetime(2027, 6, 1, 12, tzinfo=ZoneInfo("Europe/Moscow")), "user": AnonymousUser(), "departures": {}, "bookings": {}, "error": None}
    monkeypatch.setattr(timezone, "now", lambda: value["now"])
    return value


def account(name, password="Travel2027!"):
    username = {"Анна": "anna", "Борис": "boris", "Вера": "vera"}.get(name, name)
    user, created = get_user_model().objects.get_or_create(username=username)
    if created:
        user.set_password(password)
        user.save()
    return user


def tour(name="Алтай"):
    return Tour.objects.get_or_create(name=name, defaults={"slug": "altai", "organizer": account("Борис"), "direction": "Алтай", "category": "hiking", "program": "Маршрут к озеру"})[0]


def departure(state, label="Алтай 10 июня", start="2027-06-10 09:00", capacity=6):
    if label not in state["departures"]:
        starts = datetime.fromisoformat(start).replace(tzinfo=ZoneInfo("Europe/Moscow"))
        state["departures"][label] = Departure.objects.create(tour=tour(), starts_at=starts, ends_at=starts + timedelta(days=5), price=20000, capacity=capacity)
    return state["departures"][label]


def fixture_booking(state, owner, seats, label="Алтай 10 июня", alias=None):
    trip = departure(state, label)
    booking = Booking.objects.create(user=account(owner), departure=trip, seats=seats, unit_price=trip.price, request_key=uuid4())
    Departure.objects.filter(pk=trip.pk).update(reserved_seats=F("reserved_seats") + seats)
    if alias:
        state["bookings"][alias] = booking
    return booking


def arrange_free(state, label, free):
    trip = departure(state, label)
    occupied = trip.bookings.filter(status="confirmed").aggregate(total=Sum("seats"))["total"] or 0
    extra = trip.capacity - free - occupied
    assert extra >= 0, "Fixture would contradict an existing booking"
    if extra:
        fixture_booking(state, "fixture_traveler", extra, label)


def attempt(state, label, seats, key=None):
    state["error"] = None
    state["key"] = key or uuid4()
    try:
        state["last"] = create_booking(user=state["user"], departure_id=departure(state, label).pk, seats=seats, request_key=state["key"])
    except BookingError as error:
        state["error"] = error


def concurrent_calls(functions):
    barrier = Barrier(len(functions))
    def run(function):
        connections.close_all()
        try:
            barrier.wait(timeout=10)
            try:
                return function()
            except BookingError as error:
                return error
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(run, functions))


@given(parsers.parse('текущее время "{value}" в часовом поясе "{zone}"'))
def clock(state, value, zone):
    state["now"] = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(zone))


@given("посетитель не вошёл в систему")
def guest(state, client):
    client.logout()
    state["user"] = AnonymousUser()


@given("Анна вошла в систему")
def anna_logged_in(state, client):
    state["user"] = account("Анна")
    client.force_login(state["user"])


@given("Борис вошёл в систему")
def boris_logged_in(state, client):
    state["user"] = account("Борис")
    client.force_login(state["user"])


@given("Анна и Борис зарегистрированы под разными аккаунтами")
def registered_people():
    account("Анна")
    account("Борис")


@given("Анна и Вера вошли в систему под разными аккаунтами")
def two_logged_in(state):
    state["travelers"] = [account("Анна"), account("Вера")]


@given(parsers.parse('опубликован тур "{name}" организатора Бориса'))
def published_tour(name):
    tour(name)


@given(parsers.parse('у тура "{name}" есть открытый выезд "{label}" с началом "{start}" и вместимостью {capacity:d} мест'))
def open_trip(state, name, label, start, capacity):
    departure(state, label, start, capacity)


@given(parsers.re(r'на выезде "(?P<label>[^"]+)" свободно (?P<free>\d+) мест[ао]?'))
def free_places(state, label, free):
    arrange_free(state, label, int(free))


@given(parsers.parse('выезд "{label}" {status}'))
def trip_status(state, label, status):
    value = "closed" if status == "закрыт" else "archived"
    Departure.objects.filter(pk=departure(state, label).pk).update(status=value)


@given(parsers.parse('тур "{name}" отправлен в архив'))
def archive_tour(name):
    Tour.objects.filter(pk=tour(name).pk).update(is_archived=True)


@given(parsers.parse('у тура "{name}" есть другой открытый выезд "{label}" с {free:d} свободными местами'))
def second_trip(state, name, label, free):
    departure(state, label, "2027-06-20 09:00", free)


@given(parsers.parse('у Анны есть подтверждённая бронь "{alias}" на {seats:d} места на выезд "{label}"'))
def annas_named_booking(state, alias, seats, label):
    fixture_booking(state, "Анна", seats, label, alias)


@given(parsers.parse('у Анны есть подтверждённая бронь на {seats:d} место на выезд "{label}"'))
def annas_booking(state, seats, label):
    fixture_booking(state, "Анна", seats, label)


@given(parsers.parse('остальные путешественники занимают {seats:d} подтверждённых места на выезде "{label}"'))
def others_booking(state, seats, label):
    fixture_booking(state, "fixture_traveler", seats, label)


@given(parsers.parse('у Анны не было броней на выезд "{label}"'))
def no_previous_booking(state, label):
    assert not Booking.objects.filter(user=account("Анна"), departure=departure(state, label)).exists()


@given(parsers.parse('Анна получила подтверждённую бронь на {seats:d} места по запросу при {free:d} свободных местах на выезде "{label}"'))
def initial_request(state, seats, free, label):
    arrange_free(state, label, free)
    attempt(state, label, seats)
    assert state["error"] is None


@when(parsers.re(r'Анна (?:бронирует|пытается забронировать|создаёт новую отдельную бронь на) (?P<seats>\d+) мест[ао]? на выезд "(?P<label>[^"]+)"'))
def reserve(state, seats, label):
    attempt(state, label, int(seats))


@when(parsers.re(r'Анна запрашивает количество мест "(?P<value>[^"]*)" на выезд "(?P<label>[^"]+)"'))
def invalid_quantity(state, value, label):
    try:
        seats = int(value)
    except ValueError:
        seats = value
    attempt(state, label, seats)


@when(parsers.parse('посетитель пытается забронировать {seats:d} места на выезд "{label}"'))
def guest_reservation(state, client, seats, label):
    state["response"] = client.post(reverse("bookings:create", args=[departure(state, label).pk]), {"seats": seats, "request_key": uuid4()})


@when("Анна повторно отправляет тот же запрос бронирования")
def retry_request(state):
    previous = state["last"]
    attempt(state, "Алтай 10 июня", previous.seats, key=state["key"])
    assert state["last"].pk == previous.pk


@when(parsers.parse('Анна и Вера одновременно пытаются забронировать по 1 месту на выезд "{label}"'))
def concurrent_booking(state, label):
    trip = departure(state, label)
    state["results"] = concurrent_calls([
        lambda user=user: create_booking(user=user, departure_id=trip.pk, seats=1, request_key=uuid4())
        for user in state["travelers"]
    ])


@then(parsers.parse('Анна получает подтверждённую бронь на {seats:d} места на выезд "{label}"'))
def confirmed_booking(state, seats, label):
    assert state["error"] is None
    booking = state["last"]
    assert booking.user_id == state["user"].pk and booking.seats == seats
    assert booking.departure_id == departure(state, label).pk and booking.status == "confirmed"


@then(parsers.re(r'на выезде "(?P<label>[^"]+)" (?:остаётся|по-прежнему свободно|свободно(?: ровно)?) (?P<free>\d+) .+'))
def remaining_places(state, label, free):
    trip = departure(state, label)
    trip.refresh_from_db()
    assert trip.available_seats == int(free)
    confirmed = trip.bookings.filter(status="confirmed").aggregate(total=Sum("seats"))["total"] or 0
    assert trip.reserved_seats == confirmed


@then("Анна получает отказ из-за нехватки мест")
def insufficient(state):
    assert state["error"] and state["error"].code == "capacity"


@then("Анна получает отказ из-за недоступности бронирования этого выезда")
def unavailable(state):
    assert state["error"] and state["error"].code == "unavailable"


@then("Анна получает отказ из-за начала выезда")
def started(state):
    assert state["error"] and state["error"].code == "started"


@then("Анна видит требование указать целое положительное количество мест")
def quantity_error(state):
    assert state["error"] and state["error"].code == "quantity"


@then("подтверждённая бронь по этому запросу отсутствует в её списке броней")
def no_new_booking(state):
    assert not Booking.objects.filter(user=state["user"], request_key=state["key"]).exists()


@then("посетителю предлагается войти в аккаунт")
def login_required(state):
    assert state["response"].status_code == 302
    assert state["response"].url.startswith(reverse("accounts:login"))


@then("Анна получает сведения о той же подтверждённой брони")
def same_booking(state):
    assert state["error"] is None and state["last"].status == "confirmed"


@then(parsers.parse('в её списке присутствует ровно 1 бронь на выезд "{label}" на {seats:d} места'))
def one_booking(state, label, seats):
    rows = Booking.objects.filter(user=account("Анна"), departure=departure(state, label))
    assert rows.count() == 1 and rows.get().seats == seats


@then(parsers.parse('в её списке присутствуют 2 подтверждённые брони на выезд "{label}" суммарно на {seats:d} места'))
def two_bookings(state, label, seats):
    rows = Booking.objects.filter(user=account("Анна"), departure=departure(state, label), status="confirmed")
    assert rows.count() == 2 and rows.aggregate(total=Sum("seats"))["total"] == seats


@then("ровно один из пользователей получает подтверждённую бронь на 1 место")
def one_winner(state):
    successes = [result for result in state["results"] if isinstance(result, Booking)]
    assert len(successes) == 1 and successes[0].seats == 1


@then("другой пользователь получает отказ из-за нехватки мест")
def one_loser(state):
    errors = [result for result in state["results"] if isinstance(result, BookingError)]
    assert len(errors) == 1 and errors[0].code == "capacity"


def cancel_attempt(state, alias):
    state["error"] = None
    try:
        state["last"] = cancel_booking(user=state["user"], reference=state["bookings"][alias].reference)
    except BookingError as error:
        state["error"] = error


@when(parsers.parse('Анна отменяет свою бронь "{alias}"'))
@when(parsers.parse('Анна пытается отменить свою бронь "{alias}"'))
@when(parsers.parse('Анна повторно пытается отменить бронь "{alias}"'))
@when(parsers.parse('Борис пытается отменить бронь Анны "{alias}"'))
def cancel(state, alias):
    cancel_attempt(state, alias)


@given(parsers.parse('Анна уже отменила свою бронь "{alias}"'))
def previously_cancelled(state, alias):
    cancel_attempt(state, alias)
    assert state["error"] is None


@given(parsers.parse('бронирование выезда "{label}" закрыто организатором'))
def close_sales(state, label):
    Departure.objects.filter(pk=departure(state, label).pk).update(status="closed")


@when(parsers.parse('посетитель пытается отменить бронь "{alias}"'))
def guest_cancellation(state, client, alias):
    state["response"] = client.post(reverse("bookings:cancel", args=[state["bookings"][alias].reference]))


@when(parsers.parse('Анна одновременно отправляет два запроса отмены одной брони "{alias}"'))
def simultaneous_cancellation(state, alias):
    user = account("Анна")
    reference = state["bookings"][alias].reference
    state["results"] = concurrent_calls([lambda: cancel_booking(user=user, reference=reference)] * 2)
    assert all(isinstance(result, Booking) for result in state["results"])


@then(parsers.parse('бронь "{alias}" показана в её списке в состоянии "отменена"'))
@then(parsers.parse('бронь "{alias}" остаётся в состоянии "отменена"'))
def cancelled_booking(state, client, alias):
    booking = state["bookings"][alias]
    booking.refresh_from_db()
    assert booking.status == "cancelled" and booking.cancelled_at is not None
    response = client.get(reverse("bookings:mine"))
    assert response.status_code == 200
    assert booking.code in response.content.decode() and "Отменена" in response.content.decode()


@then(parsers.parse('бронь Анны "{alias}" остаётся подтверждённой на {seats:d} места'))
@then(parsers.parse('бронь "{alias}" остаётся подтверждённой на {seats:d} места'))
def still_confirmed(state, alias, seats):
    booking = state["bookings"][alias]
    booking.refresh_from_db()
    assert booking.status == "confirmed" and booking.seats == seats


@then("Борис получает отказ в отмене чужой брони")
def forbidden_cancellation(state):
    assert state["error"] and state["error"].code == "permission"


@then(parsers.parse('брони остальных путешественников по-прежнему подтверждают {seats:d} места'))
def others_unchanged(state, seats):
    assert Booking.objects.filter(user=account("fixture_traveler"), status="confirmed").aggregate(total=Sum("seats"))["total"] == seats


@then(parsers.parse('организатор видит на выезде "{label}" {free:d} свободных места'))
def organizer_availability(state, label, free):
    remaining_places(state, label, free)


@then(parsers.parse('новые бронирования выезда "{label}" остаются недоступны'))
def sales_still_closed(state, label):
    assert Departure.objects.get(pk=departure(state, label).pk).status == "closed"


@given(parsers.parse('логин "{username}" свободен'))
def free_username(username):
    assert not get_user_model().objects.filter(username=username).exists()


@given(parsers.parse('зарегистрирован пользователь с логином "{username}"'))
def existing_username(username):
    account(username)


@given(parsers.parse('зарегистрирован пользователь "{username}" с паролем "{password}"'))
def existing_account(username, password):
    account(username, password)


@given(parsers.parse('пользователь вошёл в систему под логином "{username}"'))
def logged_in_as(state, client, username):
    state["user"] = account(username)
    client.force_login(state["user"])


@given(parsers.parse('пользователь "{username}" завершил свой сеанс'))
def logged_out(state, client, username):
    client.logout()
    state["user"] = AnonymousUser()


@given(parsers.parse('пользователю "{first}" принадлежит бронь "{first_alias}", а пользователю "{second}" принадлежит бронь "{second_alias}"'))
def two_personal_bookings(state, first, first_alias, second, second_alias):
    fixture_booking(state, first, 1, alias=first_alias)
    fixture_booking(state, second, 1, alias=second_alias)


def registration(state, client, username, password, confirmation):
    state["attempt_username"] = username
    state["response"] = client.post(reverse("accounts:register"), {"username": username, "password1": password, "password2": confirmation})


@when(parsers.parse('посетитель регистрируется с логином "{username}", паролем "{password}" и подтверждением "{confirmation}"'))
def submit_registration(state, client, username, password, confirmation):
    registration(state, client, username, password, confirmation)


@when("посетитель отправляет следующие данные регистрации")
def incomplete_registration(state, client, datatable):
    data = dict(zip(datatable[0], datatable[1]))
    registration(state, client, data["логин"], data["пароль"], data["подтверждение"])


@when(parsers.parse('посетитель входит с логином "{username}" и паролем "{password}"'))
def submit_login(state, client, username, password):
    state["response"] = client.post(reverse("accounts:login"), {"username": username, "password": password})


@when("посетитель пытается просмотреть свои бронирования")
def guest_personal_bookings(state, client):
    state["response"] = client.get(reverse("bookings:mine"))


@when("пользователь выходит из аккаунта")
def logout(state, client):
    state["response"] = client.post(reverse("accounts:logout"))


@then("посетитель получает подтверждение регистрации")
def registered_successfully(state):
    assert state["response"].status_code == 302
    assert get_user_model().objects.filter(username=state["attempt_username"]).exists()


@then(parsers.parse('посетитель вошёл в систему под логином "{username}"'))
def authenticated(client, username):
    assert int(client.session["_auth_user_id"]) == account(username).pk


@then("список его бронирований доступен и пуст")
@then("список его бронирований доступен")
def personal_bookings_available(client):
    response = client.get(reverse("bookings:mine"))
    assert response.status_code == 200
    assert len(response.context["bookings"]) == 0


@then("посетитель видит сообщение о занятом логине")
def taken_username(state):
    assert "username" in state["response"].context["form"].errors


@then("посетитель видит ошибку несовпадения паролей")
@then("посетитель видит требование пароля длиной не менее 8 символов")
def invalid_password(state):
    assert "password2" in state["response"].context["form"].errors


@then(parsers.parse('посетитель видит ошибку обязательного поля "{field}"'))
def required_registration_field(state, field):
    key = {"логин": "username", "пароль": "password1", "подтверждение": "password2"}[field]
    assert key in state["response"].context["form"].errors


@then("учётная запись по этой попытке регистрации не создана")
def no_account_created(state):
    assert not get_user_model().objects.filter(username=state["attempt_username"]).exists()


@then("посетитель остаётся неавторизованным")
@then("пользователь становится неавторизованным")
def not_authenticated(client):
    assert "_auth_user_id" not in client.session


@then('посетитель видит сообщение "Неверный логин или пароль"')
def invalid_credentials(state):
    assert "Неверный логин или пароль" in state["response"].content.decode()


@then("сведения о бронированиях не отображаются")
def no_booking_disclosure(state):
    assert state["response"].status_code == 302


@then("при новом запросе своих бронирований ему предлагается войти в аккаунт")
def logout_effective(client):
    response = client.get(reverse("bookings:mine"))
    assert response.status_code == 302 and response.url.startswith(reverse("accounts:login"))


@then(parsers.parse('в списке его бронирований присутствует только бронь "{alias}"'))
def only_current_account_booking(state, client, alias):
    response = client.get(reverse("bookings:mine"))
    assert list(response.context["bookings"].values_list("pk", flat=True)) == [state["bookings"][alias].pk]
