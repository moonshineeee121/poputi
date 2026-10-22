from collections import OrderedDict
import unicodedata
from django.db.models import F, Prefetch, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from .forms import SearchForm
from .models import Departure, Tour


def open_departures():
    return Departure.objects.filter(tour__is_archived=False, status=Departure.Status.OPEN, starts_at__gt=timezone.now())


def home(request):
    form = SearchForm(request.GET or None)
    departures = open_departures().select_related("tour__organizer")
    sort = "date"
    if request.GET:
        if form.is_valid():
            data = form.cleaned_data
            if data["q"]:
                query = unicodedata.normalize("NFKC", data["q"]).casefold()
                departures = departures.filter(Q(tour__name_search__contains=query) | Q(tour__direction_search__contains=query))
            if data["category"]:
                departures = departures.filter(tour__category=data["category"])
            if data["date_from"]:
                departures = departures.filter(starts_at__date__gte=data["date_from"])
            if data["date_to"]:
                departures = departures.filter(starts_at__date__lte=data["date_to"])
            if data["price_from"] is not None:
                departures = departures.filter(price__gte=data["price_from"])
            if data["price_to"] is not None:
                departures = departures.filter(price__lte=data["price_to"])
            if data["guests"]:
                departures = departures.filter(capacity__gte=F("reserved_seats") + data["guests"])
            sort = data["sort"] or "date"
        else:
            departures = departures.none()
    ordering = {"date": ("starts_at", "tour__name"), "price": ("price", "starts_at", "tour__name"), "-price": ("-price", "starts_at", "tour__name")}[sort]
    cards = OrderedDict()
    for departure in departures.order_by(*ordering):
        if departure.tour_id not in cards:
            cards[departure.tour_id] = {"tour": departure.tour, "departure": departure, "price": departure.price, "count": 0}
        card = cards[departure.tour_id]
        card["price"] = min(card["price"], departure.price)
        card["count"] += 1
    # Published descriptions remain discoverable even when no future departure exists.
    if not request.GET:
        for tour in Tour.objects.filter(is_archived=False).select_related("organizer").exclude(pk__in=cards):
            cards[tour.pk] = {"tour": tour, "departure": None, "price": None, "count": 0}
    destinations = Tour.objects.filter(is_archived=False).order_by("pk")[:4]
    return render(request, "tours/home.html", {
        "cards": list(cards.values()), "search": form, "sort": sort,
        "categories": Tour.Category.choices, "destinations": destinations,
        "tour_count": Tour.objects.filter(is_archived=False).count(),
        "departure_count": open_departures().count(),
        "filtered": bool(request.GET),
    })


def detail_response(request, tour, form=None, selected_departure=None, status=200):
    from bookings.forms import BookingForm
    departures = list(open_departures().filter(tour=tour))
    selected = selected_departure or next((d for d in departures if d.available_seats > 0), departures[0] if departures else None)
    return render(request, "tours/detail.html", {
        "tour": tour, "departures": departures,
        "selected": selected, "booking_form": form if form is not None else BookingForm(),
    }, status=status)


def detail(request, slug):
    tour = get_object_or_404(Tour.objects.select_related("organizer"), slug=slug, is_archived=False)
    return detail_response(request, tour)
