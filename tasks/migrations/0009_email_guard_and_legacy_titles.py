from django.db import migrations

def preserve_titles(apps,schema_editor):
    Result=apps.get_model('tasks','TestResult')
    for result in Result.objects.select_related('test').all():
        result.title_snapshot=result.test.title if result.test else 'Удалённый тест'
        result.save(update_fields=['title_snapshot'])

# Historical duplicates remain untouched. Prevent new case-insensitive collisions,
# including writes outside the registration form (SQLite serializes writers).
INSERT_TRIGGER="""CREATE TRIGGER account_email_unique_insert BEFORE INSERT ON auth_user
WHEN trim(NEW.email) <> '' AND EXISTS(SELECT 1 FROM auth_user WHERE lower(trim(email))=lower(trim(NEW.email)))
BEGIN SELECT RAISE(ABORT, 'Email already exists'); END"""
UPDATE_TRIGGER="""CREATE TRIGGER account_email_unique_update BEFORE UPDATE OF email ON auth_user
WHEN lower(trim(NEW.email)) <> lower(trim(OLD.email)) AND trim(NEW.email) <> ''
AND EXISTS(SELECT 1 FROM auth_user WHERE id<>NEW.id AND lower(trim(email))=lower(trim(NEW.email)))
BEGIN SELECT RAISE(ABORT, 'Email already exists'); END"""
class Migration(migrations.Migration):
    dependencies=[('tasks','0008_portfolio_attempts')]
    operations=[migrations.RunPython(preserve_titles,migrations.RunPython.noop),
        migrations.RunSQL(INSERT_TRIGGER,'DROP TRIGGER IF EXISTS account_email_unique_insert'),
        migrations.RunSQL(UPDATE_TRIGGER,'DROP TRIGGER IF EXISTS account_email_unique_update')]
