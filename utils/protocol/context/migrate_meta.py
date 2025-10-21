from pathlib import Path
import json
import datetime
import shutil
from typing import Dict, List, Optional

from .manager import ensure_context_store_for_apps


class MetaMigrator:
    """간단한 페이사드 클래스로 migrate_meta_files 함수를 래핑합니다.

    기존 코드가 MetaMigrator를 기대하므로 이 클래스를 제공하여 하위호환성을 유지합니다.
    """
    def __init__(self, project_root: Optional[str] = None, backup: bool = True, merge_strategy: str = 'latest'):
        self.project_root = project_root
        self.backup = backup
        self.merge_strategy = merge_strategy

    def migrate(self) -> Dict[str, Dict]:
        return migrate_meta_files(project_root=self.project_root, backup=self.backup, merge_strategy=self.merge_strategy)

    # 편의 메서드 이름
    def run(self) -> Dict[str, Dict]:
        return self.migrate()


def _atomic_write(path: Path, data: str):
    """원자적 파일 쓰기를 위한 헬퍼 함수"""
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(data)
    tmp.replace(path)


def migrate_meta_files(
    project_root: Optional[str] = None, 
    backup: bool = True, 
    merge_strategy: str = 'latest'
) -> Dict[str, Dict]:
    """각 앱의 context_store 내 '*.meta.json' 파일들을 읽어 통합 meta.json으로 병합합니다.

    Args:
        project_root: discover_apps에 전달할 루트(없으면 manager._infer_project_root 사용)
        backup: True면 원본 .meta.json들을 context_store/meta_backups/ 으로 이동
        merge_strategy: 'latest' (같은 파일명 충돌 시 최신 파일 사용) 또는 'merge' (딕셔너리 병합)

    Returns:
        {app_name: {'migrated': True/False, 'sources': [src_filenames], 'meta_path': str}}
    """
    results: Dict[str, Dict] = {}
    app_stores = ensure_context_store_for_apps(project_root)

    for app_name, cs_path in app_stores.items():
        cs_dir = Path(cs_path)
        res = {
            'migrated': False, 
            'sources': [], 
            'meta_path': None, 
            'errors': []
        }
        
        try:
            meta_files = list(cs_dir.glob('*.meta.json'))
            if not meta_files:
                results[app_name] = res
                continue

            files_map: Dict[str, Dict] = {}
            sources: List[str] = []

            for mf in meta_files:
                try:
                    with mf.open('r', encoding='utf-8') as f:
                        obj = json.load(f)
                except Exception as e:
                    res['errors'].append(f'failed_read:{mf.name}:{e}')
                    continue

                orig_name = mf.name.rsplit('.meta.json', 1)[0]
                sources.append(mf.name)

                if orig_name not in files_map:
                    files_map[orig_name] = {
                        'meta': obj, 
                        'mtime': mf.stat().st_mtime
                    }
                else:
                    # 충돌 처리
                    if merge_strategy == 'latest':
                        if mf.stat().st_mtime >= files_map[orig_name]['mtime']:
                            files_map[orig_name] = {
                                'meta': obj, 
                                'mtime': mf.stat().st_mtime
                            }
                    else:
                        # merge: 단순 dict 업데이트(기존 키 덮어씀)
                        try:
                            existing_meta = files_map[orig_name]['meta']
                            if isinstance(existing_meta, dict) and isinstance(obj, dict):
                                existing_meta.update(obj)
                                files_map[orig_name]['meta'] = existing_meta
                            else:
                                files_map[orig_name] = {
                                    'meta': obj, 
                                    'mtime': mf.stat().st_mtime
                                }
                        except Exception:
                            files_map[orig_name] = {
                                'meta': obj, 
                                'mtime': mf.stat().st_mtime
                            }

            # 준비된 구조로 meta.json 생성
            meta_out = {
                'merged_at': datetime.datetime.now().isoformat(),
                'files': {k: v['meta'] for k, v in files_map.items()},
                'sources': sources,
            }

            meta_path = cs_dir / 'meta.json'
            try:
                json_str = json.dumps(meta_out, ensure_ascii=False, indent=2)
                _atomic_write(meta_path, json_str)
            except Exception as e:
                res['errors'].append(f'failed_write_meta:{e}')
                results[app_name] = res
                continue

            # 백업(이동)
            if backup:
                backup_dir = cs_dir / 'meta_backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                
                for mf in meta_files:
                    try:
                        target = backup_dir / f'{mf.name}.{timestamp}'
                        shutil.move(str(mf), str(target))
                    except Exception as e:
                        res['errors'].append(f'failed_backup:{mf.name}:{e}')

            res['migrated'] = True
            res['sources'] = sources
            res['meta_path'] = str(meta_path)
            
        except Exception as e:
            res['errors'].append(str(e))
        
        results[app_name] = res

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Migrate per-file .meta.json files into unified meta.json in each context_store'
    )
    parser.add_argument(
        '--root', 
        help='project root path', 
        default=None
    )
    parser.add_argument(
        '--no-backup', 
        action='store_true', 
        help='do not move original .meta.json files to meta_backups'
    )
    parser.add_argument(
        '--merge', 
        choices=['latest', 'merge'], 
        default='latest', 
        help='merge strategy for conflicting meta entries'
    )
    
    args = parser.parse_args()

    results = migrate_meta_files(
        project_root=args.root, 
        backup=not args.no_backup, 
        merge_strategy=args.merge
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
