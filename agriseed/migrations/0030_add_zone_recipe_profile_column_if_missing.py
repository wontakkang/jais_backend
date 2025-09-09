# 새 마이그레이션: 존재하지 않으면 agriseed_zone.recipe_profile_id 컬럼을 추가합니다.
from django.db import migrations


def add_recipe_profile_column(apps, schema_editor):
    conn = schema_editor.connection
    cursor = conn.cursor()
    table = 'agriseed_zone'
    column = 'recipe_profile_id'

    try:
        cursor.execute("PRAGMA table_info('%s')" % table)
        existing = [row[1] for row in cursor.fetchall()]
    except Exception:
        existing = []

    if column in existing:
        return

    # SQLite: 외래키 제약을 안전하게 추가하기 어렵기 때문에 NULL 허용 integer 컬럼만 추가
    cursor.execute("ALTER TABLE %s ADD COLUMN %s integer;" % (table, column))
    try:
        conn.commit()
    except Exception:
        pass


def noop_reverse(apps, schema_editor):
    # 되돌리기 시 안전하게 아무 동작도 하지 않음 (SQLite에서 열 삭제는 복잡하므로 수동 처리 권장)
    return


class Migration(migrations.Migration):

    dependencies = [
        ('agriseed', '0029_remove_zone_daily_watering_count_and_more'),
    ]

    operations = [
        migrations.RunPython(add_recipe_profile_column, noop_reverse),
    ]
