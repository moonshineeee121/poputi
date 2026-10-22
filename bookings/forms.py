import uuid
from django import forms


class BookingForm(forms.Form):
    seats = forms.IntegerField(label="Количество участников", min_value=1, initial=1, widget=forms.NumberInput(attrs={"inputmode": "numeric", "data-seats": ""}))
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
