from django import forms
from .models import Tour


class SearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=120, label="Направление")
    category = forms.ChoiceField(required=False, choices=[("", "Все путешествия"), *Tour.Category.choices])
    date_from = forms.DateField(required=False, label="Дата начала от", widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, label="Дата начала до", widget=forms.DateInput(attrs={"type": "date"}))
    price_from = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label="Цена от")
    price_to = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2, label="Цена до")
    guests = forms.IntegerField(required=False, min_value=1, max_value=100, label="Участники")
    sort = forms.ChoiceField(required=False, choices=[("date", "Сначала ближайшие"), ("price", "Сначала дешевле"), ("-price", "Сначала дороже")])

    def clean(self):
        data = super().clean()
        for start, end, label in [("date_from", "date_to", "дат"), ("price_from", "price_to", "цен")]:
            if data.get(start) is not None and data.get(end) is not None and data[start] > data[end]:
                self.add_error(end, f"Проверьте диапазон {label}: начало больше окончания.")
        return data
