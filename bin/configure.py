#!/usr/bin/env python3
"""File installation only. Never fetch, execute a repository, or unlock a vault."""
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime

home = Path.home()
config = home / '.config/dotfiles'


def backup(path):
    stamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    target = path.with_name(path.name + '.bak.' + stamp)
    shutil.copy2(path, target, follow_symlinks=True)
    return target


def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == source.resolve():
        return
    if target.exists() or target.is_symlink():
        # Preserve arbitrary links and user files as well as regular files.
        stamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        target.rename(target.with_name(target.name + '.bak.' + stamp))
    target.symlink_to(source, target_is_directory=source.is_dir())


def block(path, name, contents, prepend=False, preserve_link=False, preserve_legacy_contents=False):
    begin, end = f'# >>> dotfiles {name} >>>', f'# <<< dotfiles {name} <<<'
    old = path.read_text() if path.exists() else ''
    # Migrate the legacy whole-file symlink without editing its source repository.
    if path.is_symlink() and not preserve_link:
        legacy = str(path.resolve()).endswith(('/links/zsh/zshrc', '/links/ssh/config'))
        path.rename(path.with_name(path.name + '.bak.' + datetime.now().strftime('%Y%m%d%H%M%S%f')))
        if legacy and not preserve_legacy_contents:
            old = ''
    if (begin in old) != (end in old):
        raise SystemExit(f'Incomplete managed block in {path}; repair it first.')
    if begin in old:
        start = old.index(begin)
        finish = old.index(end, start) + len(end)
        old = old[:start] + old[finish:].lstrip('\n')
    managed = f'{begin}\n{contents}\n{end}\n'
    new = managed + old if prepend else old.rstrip('\n') + '\n' + managed
    if path.exists() and path.read_text() == new:
        return
    if path.exists():
        backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new)


def safe_ssh_copy(source, target):
    # OpenSSH rejects a config reached through a group/world-writable checkout
    # (e.g. WSL /mnt/c). Copy with controlled permissions instead of linking it.
    import tempfile
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    content = source.read_text()
    if target.is_file() and not target.is_symlink() and target.read_text() == content:
        target.chmod(0o600)
        return
    if target.exists() or target.is_symlink():
        target.rename(target.with_name(target.name + '.bak.' + datetime.now().strftime('%Y%m%d%H%M%S%f')))
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix='.dotfiles-ssh-')
    try:
        with os.fdopen(descriptor, 'w') as output:
            output.write(content)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(repo, mode):
    from host_inventory import references
    preserve_existing=bool(references())
    config.mkdir(parents=True, exist_ok=True)
    shell=config/'shell.zsh'
    if preserve_existing and (home/'.zshrc').exists() and shell.resolve()!=(repo/'links/zsh/dotfiles.zsh').resolve():
        # Reference adoption does not transfer ownership of the legacy shell.
        # Explicitly applied new selections are an additive source after it.
        import shlex
        block(home/'.zshrc','dashboard extras','source '+shlex.quote(str(repo/'links/zsh/dotfiles.zsh')),preserve_legacy_contents=True)
    else:
        link(repo / 'links/zsh/dotfiles.zsh', shell)
        link(repo / 'links/zsh/zshrc', config / 'zshrc')
        block(home / '.zshrc', 'shell', 'source "$HOME/.config/dotfiles/zshrc"',preserve_legacy_contents=preserve_existing)
    safe_ssh_copy(repo / 'links/ssh/config', home / '.ssh/config.d/dotfiles.conf')
    for key in (repo / 'links/ssh/keys').glob('*.pub'):
        link(key, home / '.ssh/keys' / key.name)
    ssh_include=('Host *\n' if preserve_existing else '')+'Include ~/.ssh/config.d/dotfiles.conf\nHost *'
    block(home / '.ssh/config', 'ssh', ssh_include, prepend=not preserve_existing,preserve_legacy_contents=preserve_existing)
    (home / '.ssh/config').chmod(0o600)
    import subprocess
    # A stable include path avoids accumulating paths when the checkout is moved.
    link(repo / 'links/git', config / 'git')
    include = str(config / 'git/config')
    existing = subprocess.run(['git', 'config', '--global', '--get-all', 'include.path'], text=True, capture_output=True).stdout.splitlines()
    legacy = str(repo / 'links/git/config')
    if legacy in existing:
        subprocess.run(['git', 'config', '--global', '--fixed-value', '--unset-all', 'include.path', legacy], check=True)
    # Keep the managed include after existing global identities/helpers so gitdir
    # policies take precedence. Local repository/command overrides remain Git's policy.
    explicit = os.environ.get('GIT_CONFIG_GLOBAL')
    xdg = Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config'))) / 'git/config'
    global_path = Path(explicit).expanduser() if explicit else home / '.gitconfig' if (home / '.gitconfig').exists() or not xdg.exists() else xdg
    original = global_path.read_text() if global_path.exists() else ''
    complete = original.rstrip().endswith('# <<< dotfiles git <<<') and existing.count(include) == 1
    if not complete:
        if include in existing:
            subprocess.run(['git', 'config', '--global', '--fixed-value', '--unset-all', 'include.path', include], check=True)
        import json
        block(global_path, 'git', '[include]\n    path = ' + json.dumps(include, ensure_ascii=False), preserve_link=True)
    if mode == 'container':
        return
    import json
    settings = config / 'dashboard/settings.json'
    saved = json.loads(settings.read_text()) if settings.exists() else {}
    enabled = saved.get('features', saved)
    def optional_link(feature, source, target):
        if enabled.get(feature, {}).get('enabled', False):
            link(source, target)
        elif target.is_symlink() and target.resolve() == source.resolve():
            target.unlink()
            backups = sorted(target.parent.glob(target.name + '.bak.*'))
            if backups:
                backups[-1].rename(target)
    optional_link('zellij', repo / 'links/terminal/zellij/config.kdl', home / '.config/zellij/config.kdl')
    for name in ('keymap.toml', 'yazi.toml'):
        optional_link('yazi', repo / 'links/yazi' / name, home / '.config/yazi' / name)
    if sys.platform == 'darwin':
        optional_link('yazi', repo / 'links/apps/Yazi.app', home / 'Applications/Yazi.app')
    # Color UI edits local data, never tracked paths in the public repository.
    for name, source in [('ghostty.conf', 'ghostty/project-colors.conf'), ('iterm.conf', 'iterm2/tab-colors.conf')]:
        target = config / 'terminal' / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / 'links/terminal' / source, target)


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'install':
        install(Path(sys.argv[2]).resolve(), sys.argv[3])
    elif action == 'attach':
        source = Path(sys.argv[2]).expanduser().resolve()
        for required in ('git/config', 'ssh/config', 'secrets.json', 'shell.zsh'):
            if not (source / required).is_file():
                raise SystemExit(f'Missing private configuration: {required}')
        config.mkdir(parents=True, exist_ok=True)
        link(source, config / 'private')
        print('Private configuration attached. Open a new zsh, then run bws.')
    else:
        raise SystemExit('Unknown action')
