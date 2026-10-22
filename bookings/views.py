from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from tours.models import Departure
from tours.views import detail_response
from .forms import BookingForm
from .models import Booking
from .services import BookingError, cancel_booking, create_booking


@login_required
def mine(request):
    bookings = request.user.bookings.select_related("departure__tour")
    return render(request, "bookings/mine.html", {"bookings": bookings, "now": timezone.now()})


@login_required
@require_POST
def create(request, departure_id):
    departure = get_object_or_404(Departure.objects.select_related("tour"), pk=departure_id)
    form = BookingForm(request.POST)
    if form.is_valid():
        try:
            booking = create_booking(user=request.user, departure_id=departure.pk, **form.cleaned_data)
        except BookingError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Бронь {booking.code} подтверждена. До встречи в путешествии!")
            return redirect("bookings:mine")
    return detail_response(request, departure.tour, form=form, selected_departure=departure, status=400)


@login_required
@require_POST
def cancel(request, reference):
    if not Booking.objects.filter(reference=reference, user=request.user).exists():
        raise Http404
    try:
        cancel_booking(user=request.user, reference=reference)
    except BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Бронь отменена. Места снова доступны путешественникам.")
    return redirect("bookings:mine")
