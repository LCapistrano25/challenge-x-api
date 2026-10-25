from django.db import migrations

# ODS aceitas na edição 2026 (RF04), com título e descrição oficiais da Agenda 2030.
SDGS = [
    (
        1,
        "Erradicação da Pobreza",
        "Acabar com a pobreza em todas as suas formas, em todos os lugares.",
    ),
    (
        2,
        "Fome Zero e Agricultura Sustentável",
        "Acabar com a fome, alcançar a segurança alimentar e melhoria da nutrição "
        "e promover a agricultura sustentável.",
    ),
    (
        3,
        "Saúde e Bem-Estar",
        "Assegurar uma vida saudável e promover o bem-estar para todas e todos, "
        "em todas as idades.",
    ),
    (
        9,
        "Indústria, Inovação e Infraestrutura",
        "Construir infraestruturas resilientes, promover a industrialização "
        "inclusiva e sustentável e fomentar a inovação.",
    ),
    (
        16,
        "Paz, Justiça e Instituições Eficazes",
        "Promover sociedades pacíficas e inclusivas para o desenvolvimento "
        "sustentável, proporcionar o acesso à justiça para todos e construir "
        "instituições eficazes, responsáveis e inclusivas em todos os níveis.",
    ),
]


def seed(apps, schema_editor):
    Sdg = apps.get_model("core", "Sdg")
    for number, title, description in SDGS:
        Sdg.objects.update_or_create(
            number=number, defaults={"title": title, "description": description}
        )


def unseed(apps, schema_editor):
    apps.get_model("core", "Sdg").objects.filter(
        number__in=[number for number, _, _ in SDGS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
