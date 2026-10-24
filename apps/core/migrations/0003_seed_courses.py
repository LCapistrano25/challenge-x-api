from django.db import migrations

# Cursos da UniCatólica (ensalamento 2026/2) e quantidade de períodos (RN10).
COURSES = [
    ("Administração", 8),
    ("Agronomia", 10),
    ("Arquitetura e Urbanismo", 10),
    ("Biomedicina", 10),
    ("Ciências Contábeis", 8),
    ("Direito", 10),
    ("Enfermagem", 10),
    ("Engenharia Civil", 10),
    ("Engenharia de Software", 8),
    ("Farmácia", 10),
    ("Inteligência Artificial", 10),
    ("Medicina Veterinária", 10),
    ("Psicologia", 10),
    ("Terapia Ocupacional", 10),
    ("Zootecnia", 10),
]


def seed(apps, schema_editor):
    Course = apps.get_model("core", "Course")
    for name, term_count in COURSES:
        Course.objects.update_or_create(name=name, defaults={"term_count": term_count})


def unseed(apps, schema_editor):
    apps.get_model("core", "Course").objects.filter(
        name__in=[name for name, _ in COURSES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_seed_sdgs"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
