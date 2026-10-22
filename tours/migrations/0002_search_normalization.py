import unicodedata
from django.db import migrations, models


def fill_search_fields(apps, schema_editor):
    Tour = apps.get_model("tours", "Tour")
    for tour in Tour.objects.using(schema_editor.connection.alias).all().iterator():
        Tour.objects.using(schema_editor.connection.alias).filter(pk=tour.pk).update(
            name_search=unicodedata.normalize("NFKC", tour.name).casefold(),
            direction_search=unicodedata.normalize("NFKC", tour.direction).casefold(),
        )


class Migration(migrations.Migration):
    dependencies = [("tours", "0001_initial")]
    operations = [
        migrations.AddField(model_name="tour", name="name_search", field=models.TextField(default="", editable=False)),
        migrations.AddField(model_name="tour", name="direction_search", field=models.TextField(default="", editable=False)),
        migrations.RunPython(fill_search_fields, migrations.RunPython.noop),
    ]
