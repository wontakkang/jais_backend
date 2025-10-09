from django.db import migrations


def copy_memorygroups(apps, schema_editor):
    CoreMemoryGroup = apps.get_model('corecode', 'MemoryGroup')
    LSISMemoryGroup = apps.get_model('LSISsocket', 'MemoryGroup')

    # corecode.MemoryGroup에 있는 레코드를 순회하여 LSISsocket.MemoryGroup에 같은 PK로 없는 경우 생성
    for core in CoreMemoryGroup.objects.all():
        try:
            if not LSISMemoryGroup.objects.filter(pk=core.pk).exists():
                # core 모델과 필드가 완전히 일치하지 않으므로 필요한 필드만 복사합니다.
                LSISMemoryGroup.objects.create(
                    id=core.pk,
                    name=getattr(core, 'name', None),
                    description=None,
                    size_byte=getattr(core, 'size_byte', 0),
                )
        except Exception:
            # 실패한 레코드는 건너뜁니다(로그가 필요하면 예외 내용을 출력하도록 수정 가능)
            continue


class Migration(migrations.Migration):

    dependencies = [
        ('LSISsocket', '0004_delete_memorygroup_memorygroup_variable'),
        ('corecode', '0014_memorygroup_adapter'),
    ]

    operations = [
        migrations.RunPython(copy_memorygroups, reverse_code=migrations.RunPython.noop),
    ]
