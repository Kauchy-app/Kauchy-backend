from django.db import migrations


def mark_existing_complete(apps, schema_editor):
    # Existing users were all created via email/password signup, so they
    # already have phone/institute/role — don't prompt them for completion.
    CustomUserModel = apps.get_model("account", "CustomUserModel")
    CustomUserModel.objects.update(profile_completed=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0010_customusermodel_profile_completed"),
    ]

    operations = [
        migrations.RunPython(mark_existing_complete, noop),
    ]
