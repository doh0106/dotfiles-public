#!/usr/bin/env python3
"""Offline smoke checks using an isolated HOME. Run with python3 tests/smoke.py."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[1]


def run(args, env, success=True):
    result = subprocess.run([str(x) for x in args], env=env, text=True, capture_output=True)
    if success and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


with tempfile.TemporaryDirectory(prefix='dotfiles-smoke-') as directory:
    home = Path(directory)
    env = dict(os.environ, HOME=directory, GIT_CONFIG_NOSYSTEM='1')
    env.pop('GIT_CONFIG_GLOBAL', None)
    (home / '.ssh').mkdir()
    (home / '.ssh/config').write_text('Host existing\n    HostName example.org\n')
    (home / '.zshrc').write_text('export EXISTING_SETTING=preserved\n')
    run(['bash', repo / 'bin/bootstrap.sh'], env)
    paths = [home / '.ssh/config', home / '.zshrc', home / '.gitconfig']
    before = [p.read_text() for p in paths]
    run(['bash', repo / 'bin/bootstrap.sh'], env)
    assert before == [p.read_text() for p in paths]
    assert 'Host existing' in paths[0].read_text()
    assert 'EXISTING_SETTING' in paths[1].read_text()
    run(['bash', repo / 'bin/verify.sh'], env)
    run(['zsh', '-c', 'source "$HOME/.zshrc"; [[ "$EXISTING_SETTING" == preserved ]]'], env)
    overlay = home / 'overlay'
    for name in ('git', 'ssh'):
        (overlay / name).mkdir(parents=True)
    (overlay / 'git/config').write_text('[alias]\n    overlay-check = status\n')
    (overlay / 'ssh/config').write_text('Host example-private\n    HostName example.org\nHost *\n')
    (overlay / 'secrets.json').write_text(json.dumps({'secrets': []}))
    (overlay / 'shell.zsh').write_text('export PRIVATE_OVERLAY_TEST=loaded\n')
    run(['bash', repo / 'bin/attach-private.sh', overlay], env)
    assert run(['git', 'config', '--get', 'alias.overlay-check'], env).stdout.strip() == 'status'
    run(['zsh', '-c', 'source "$HOME/.zshrc"; [[ "$PRIVATE_OVERLAY_TEST" == loaded ]]'], env)
    print('PASS: repeat installation, existing settings, public HTTPS and identity blocking, private overlay')
