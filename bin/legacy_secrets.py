"""Read bws manifest registrations only. Never source scripts or fetch secret values."""
import hashlib
import json
import os
from pathlib import Path
import stat
import configuration as cfg


def registrations():
    explicit=os.environ.get('DOTFILES_SECRETS_MANIFEST')
    roots=[Path(os.environ['DOTFILES_DIR']).expanduser()] if os.environ.get('DOTFILES_DIR') else []
    roots += [cfg.REPO,Path.home()/'dotfiles',Path.home()/'.dotfiles']
    paths=[Path(explicit).expanduser()] if explicit else [root/'secrets.json' for root in roots]
    entries={};warnings=[];seen=set()
    for path in paths:
        try:
            path=path.resolve()
            if path in seen:continue
            seen.add(path)
            if not path.is_relative_to(Path.home().resolve()):raise ValueError()
            info=path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>262144:raise ValueError()
            raw=json.loads(path.read_text())
            if not isinstance(raw,dict) or not isinstance(raw.get('secrets'),list) or len(raw['secrets'])>100:raise ValueError()
            skipped=0
            for row in raw['secrets']:
                if not isinstance(row,dict):skipped+=1;continue
                name=row.get('bw_name');kind=row.get('bw_type')
                if row.get('action')!='ssh-add' or kind not in ('note','sshkey') or row.get('field','private')!='private':skipped+=1;continue
                if not isinstance(name,str) or not name.strip() or len(name)>200 or any(ord(c)<32 or ord(c)==127 for c in name) or name.startswith('-'):skipped+=1;continue
                key=(name,kind)
                if key not in entries:
                    ident='bws-'+hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20]
                    entries[key]=dict(id=ident,item=name,name=name,kind=kind,purpose='ssh-key',sources=[])
                entries[key]['sources'].append(str(path))
            if skipped:warnings.append(f'{path}: SSH 키 공급 이외의 항목 {skipped}개는 실행하거나 가져오지 않습니다.')
        except FileNotFoundError:continue
        except (OSError,ValueError,UnicodeError):warnings.append(f'{path}: 등록 목록을 읽을 수 없습니다. 원본은 유지했습니다.')
    return dict(items=list(entries.values()),warnings=warnings)
