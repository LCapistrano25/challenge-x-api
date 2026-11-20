import django.db.models.functions.text
from django.db import migrations, models


def lowercase_domain_names(apps, schema_editor):
    """Passa os nomes para minúsculas antes da unicidade sem diferenciar a caixa.

    Antes desta migração o admin aceitava Catolica.edu.br e catolica.edu.br como
    domínios diferentes; se houver um par assim, a migração para com a mensagem
    abaixo em vez de quebrar na constraint.
    """
    EmailDomain = apps.get_model("accounts", "EmailDomain")
    seen = {}
    for domain in EmailDomain.objects.order_by("pk"):
        name = domain.name.strip().lower()
        if name in seen:
            raise RuntimeError(
                f"Domínios repetidos ao ignorar maiúsculas: {seen[name]!r} e "
                f"{domain.name!r}. Remova um deles antes de migrar."
            )
        seen[name] = domain.name
        if name != domain.name:
            domain.name = name
            domain.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_microsoft_id"),
    ]

    operations = [
        migrations.RunPython(lowercase_domain_names, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="emaildomain",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("name"),
                name="unique_email_domain_name_ci",
            ),
        ),
    ]
