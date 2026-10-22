from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from tours.models import Departure, Tour

DATA = [
    ("altai", "Алтай. Ближе к небу", "Республика Алтай", "hiking", "altai", 64000, 7, "Бирюзовые озёра, горные тропы и вечера у костра.", "Неспешное знакомство с Чуйским трактом.\n\nПоход к горным озёрам и панорамным перевалам.\n\nДни среди кедрового леса, прогулки по долинам и вечера у костра.", "Средняя сложность"),
    ("dagestan", "Дагестан: горы и люди", "Дагестан", "roadtrip", "dagestan", 38500, 5, "Каньоны, горные аулы и настоящее гостеприимство.", "Сулакский каньон и прогулка по бархану.\n\nГорные аулы, местная кухня и встречи с жителями.\n\nКаспийское море и вечерние прогулки по Дербенту.", "Подойдёт начинающим"),
    ("karelia", "Карелия. Режим тишины", "Карелия", "hiking", "karelia", 27900, 4, "Сосновый лес, северные озёра и время для себя.", "Прогулки по лесным тропам и скалистым берегам.\n\nЗнакомство с озёрами и водопадами Карелии.\n\nСвободный день для отдыха, фотографий и разговоров.", "Лёгкий маршрут"),
    ("baikal", "Байкал без спешки", "Озеро Байкал", "expedition", "baikal", 56900, 6, "Большая вода, островные дороги и простор до горизонта.", "Знакомство с берегами Байкала.\n\nПоездка на Ольхон и прогулки по острову.\n\nПанорамные точки, местная кухня и день у воды.", "Подойдёт начинающим"),
    ("kamchatka", "Камчатка. На край земли", "Камчатка", "expedition", "kamchatka", 119000, 9, "Вулканы, океан и ощущение другого мира.", "Побережье Тихого океана и вулканические пляжи.\n\nМаршруты по предгорьям с гидом.\n\nТермальные источники и дни среди дикой природы.", "Нужна физическая подготовка"),
    ("forest", "Выходные в горах", "Кавказ", "excursion", "georgia", 24900, 3, "Короткая поездка, после которой хочется остаться.", "Дорога к горным долинам и знакомство с группой.\n\nПрогулки с местным гидом и обед с видом на горы.\n\nСвободное утро и возвращение домой.", "Лёгкий маршрут"),
]


class Command(BaseCommand):
    help = "Добавляет демонстрационные туры и выезды без изменения существующих броней."

    def handle(self, *args, **options):
        User = get_user_model()
        organizer, created = User.objects.get_or_create(username="travel_guide", defaults={"first_name": "Александр"})
        if created:
            organizer.set_unusable_password()
            organizer.save(update_fields=["password"])
        for index, (slug, name, direction, category, image, price, days, summary, program, difficulty) in enumerate(DATA):
            tour, _ = Tour.objects.get_or_create(slug=slug, defaults={
                "organizer": organizer, "name": name, "direction": direction, "category": category,
                "image": f"img/{image}.jpg", "summary": summary, "program": program, "difficulty": difficulty,
            })
            if not tour.departures.filter(starts_at__gt=timezone.now()).exists():
                for offset in (0, 18, 36):
                    date = timezone.localdate() + timedelta(days=20 + index * 3 + offset)
                    start = timezone.make_aware(datetime.combine(date, time(9)), ZoneInfo("Europe/Moscow"))
                    Departure.objects.create(tour=tour, starts_at=start, ends_at=start + timedelta(days=days - 1, hours=9), price=price + offset * 100, capacity=8 if index % 2 else 10)
        self.stdout.write(self.style.SUCCESS(f"Готово: {Tour.objects.count()} туров, {Departure.objects.count()} выездов."))
