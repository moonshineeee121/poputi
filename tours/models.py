from decimal import Decimal
import unicodedata
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Tour(models.Model):
    class Category(models.TextChoices):
        HIKING = "hiking", "Поход"
        EXCURSION = "excursion", "Экскурсия"
        EXPEDITION = "expedition", "Экспедиция"
        ROADTRIP = "roadtrip", "Автотур"

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tours")
    name = models.CharField("Название", max_length=180)
    slug = models.SlugField("Адрес", unique=True)
    direction = models.CharField("Направление", max_length=120)
    category = models.CharField("Категория", max_length=20, choices=Category.choices)
    summary = models.CharField("Краткое описание", max_length=280, blank=True)
    program = models.TextField("Программа")
    image = models.CharField("Изображение из static", max_length=200, default="img/altai.jpg")
    difficulty = models.CharField("Сложность", max_length=80, default="Подойдёт начинающим")
    is_archived = models.BooleanField("В архиве", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name_search = models.TextField(default="", editable=False)
    direction_search = models.TextField(default="", editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "тур"
        verbose_name_plural = "туры"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("tours:detail", args=[self.slug])

    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        for source in ("name", "direction"):
            if fields is None or source in fields:
                target = f"{source}_search"
                setattr(self, target, unicodedata.normalize("NFKC", getattr(self, source)).casefold())
                if fields is not None:
                    fields = set(fields) | {target}
        if fields is not None:
            kwargs["update_fields"] = fields
        return super().save(*args, **kwargs)


class Departure(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Открыт"
        CLOSED = "closed", "Закрыт"
        ARCHIVED = "archived", "В архиве"

    tour = models.ForeignKey(Tour, on_delete=models.PROTECT, related_name="departures")
    starts_at = models.DateTimeField("Начало")
    ends_at = models.DateTimeField("Окончание")
    price = models.DecimalField("Цена за место, ₽", max_digits=10, decimal_places=2)
    capacity = models.PositiveIntegerField("Вместимость")
    reserved_seats = models.PositiveIntegerField("Занято мест", default=0, editable=False)
    status = models.CharField("Состояние", max_length=16, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "выезд"
        verbose_name_plural = "выезды"
        constraints = [
            models.CheckConstraint(condition=models.Q(capacity__gt=0), name="departure_positive_capacity"),
            models.CheckConstraint(condition=models.Q(reserved_seats__lte=models.F("capacity")), name="departure_not_overbooked"),
            models.CheckConstraint(condition=models.Q(price__gt=0), name="departure_positive_price"),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="departure_dates_ordered"),
        ]

    @property
    def available_seats(self):
        return self.capacity - self.reserved_seats

    @property
    def duration(self):
        return max(1, (timezone.localdate(self.ends_at) - timezone.localdate(self.starts_at)).days + 1)

    def clean(self):
        super().clean()
        if self.starts_at and (not self.pk or not Departure.objects.filter(pk=self.pk, starts_at=self.starts_at).exists()) and self.starts_at <= timezone.now():
            raise ValidationError({"starts_at": "Начало выезда должно быть в будущем."})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Окончание должно быть позже начала."})
        if self.capacity is not None and self.capacity < self.reserved_seats:
            raise ValidationError({"capacity": f"Уже забронировано {self.reserved_seats} мест."})
        if self.price is not None and self.price <= Decimal("0"):
            raise ValidationError({"price": "Цена должна быть положительной."})
        if self.pk and self.bookings.exists():
            previous = Departure.objects.get(pk=self.pk)
            if any(getattr(previous, field) != getattr(self, field) for field in ("starts_at", "ends_at", "price", "tour_id")):
                raise ValidationError("После первого бронирования тур, даты и цена выезда зафиксированы.")

    def save(self, *args, **kwargs):
        if not self.pk:
            self.full_clean()
            return super().save(*args, **kwargs)
        with transaction.atomic():
            previous = Departure.objects.select_for_update().get(pk=self.pk)
            self.reserved_seats = previous.reserved_seats
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tour.name} · {timezone.localtime(self.starts_at):%d.%m.%Y}"
