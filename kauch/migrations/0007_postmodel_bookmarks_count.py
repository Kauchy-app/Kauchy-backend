from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kauch', '0006_postmodel_shares_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='postmodel',
            name='bookmarks_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]