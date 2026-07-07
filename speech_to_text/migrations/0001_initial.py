from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProtectedTerm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(max_length=255, unique=True)),
                ("target", models.CharField(blank=True, max_length=255)),
                ("aliases", models.JSONField(default=list)),
                ("mode", models.CharField(default="preserve", max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "text_processing_protectedterm",
            },
        ),
        migrations.AddIndex(
            model_name="protectedterm",
            index=models.Index(fields=["is_active"], name="text_proces_is_acti_975f2b_idx"),
        ),
    ]
