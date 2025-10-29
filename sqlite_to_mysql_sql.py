# SQLite에서 MySQL로 데이터 마이그레이션용 SQL INSERT문 생성 스크립트
import os
import django
import sys
import datetime
from django.apps import apps
from django.conf import settings
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'py_backend.settings')
django.setup()

APPS = ['agriseed', 'LSISsocket', 'corecode', 'MCUnode']

def get_table_names(app_label):
    app_config = apps.get_app_config(app_label)
    models = app_config.get_models()
    return [m._meta.db_table for m in models]

def escape_mysql(val):
    if val is None:
        return 'NULL'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, datetime.datetime):
        return f"'{val.isoformat(sep=' ')}'"
    if isinstance(val, datetime.date):
        return f"'{val.isoformat()}'"
    return "'" + str(val).replace("'", "''") + "'"

def main():
    src_conn = connections['default']
    table_list = []
    for app in APPS:
        table_list.extend(get_table_names(app))
    with open('insert_data.sql', 'w', encoding='utf-8') as f:
        with src_conn.cursor() as c:
            for table in table_list:
                c.execute(f'SELECT * FROM `{table}`')
                rows = c.fetchall()
                if not rows:
                    continue
                columns = [col[0] for col in c.description]
                for row in rows:
                    values = ', '.join([escape_mysql(v) for v in row])
                    sql = f"INSERT INTO `{table}` ({', '.join(columns)}) VALUES ({values});"
                    f.write(sql + '\n')

if __name__ == '__main__':
    main()
