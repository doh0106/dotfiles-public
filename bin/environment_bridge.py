"""Optional protocol-v1 bridge. Does not load core modules into this process."""
import json
import hashlib
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading


def source_digest(root):
    paths=[root/'cli.py',*sorted((root/'environment_core').rglob('*'))]
    records=[]
    for path in paths:
        if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        if path.is_symlink():raise ValueError('installation_source_symlink')
        records.append([str(path.relative_to(root)),hashlib.sha256(path.read_bytes()).hexdigest()])
    return hashlib.sha256(json.dumps(sorted(records),separators=(',',':')).encode()).hexdigest()


def registered_locations():
    path = Path.home()/'.config/environment-core/installation.json'
    try:
        if not path.exists() or any(p.is_symlink() for p in (path,*path.parents)):return {}
        for entry in (path,path.parent):
            info=entry.stat()
            if info.st_uid!=os.geteuid() or info.st_mode&0o077:return {}
        if path.stat().st_size>16384:return {}
        data=json.loads(path.read_text())
        if not isinstance(data,dict) or set(data)!={'protocol_version','core_root','runtime_root','agent_kit_root','core_digest'} or data['protocol_version']!=1:return {}
        if not isinstance(data['core_digest'],str) or len(data['core_digest'])!=64:return {}
        for name in ('core_root','runtime_root','agent_kit_root'):
            value=data[name]
            if not isinstance(value,str) or len(value)>4096 or (value and not Path(value).is_absolute()):return {}
        return data
    except (OSError,ValueError):return {}


class EnvironmentBridge:
    def __init__(self, core=None, runtime=None, agent_kit=None, digest=None):
        self.core = Path(core).expanduser().resolve() if core else None
        self.runtime = Path(runtime).expanduser().resolve() if runtime else None
        self.agent_kit = Path(agent_kit).expanduser().resolve() if agent_kit else None
        self.digest=digest
        self.child = None
        self.lock = threading.Lock()

    def environment(self):
        # A newly opened UI does not inherit terminal authentication sessions.
        return {k: v for k, v in os.environ.items() if k in
                ('PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'LANG', 'LC_ALL', 'SYSTEMROOT')}

    def command(self):
        if self.core is None or not (self.core / 'cli.py').is_file():
            raise ValueError('environment_core_not_configured')
        if self.digest is not None and source_digest(self.core)!=self.digest:
            raise ValueError('environment_core_digest_mismatch')
        return [sys.executable, '-I', str(self.core / 'cli.py')]

    def status(self, workspace=None):
        try:
            command = self.command()
            if self.runtime: command += ['--dev-environment-root', str(self.runtime)]
            if workspace:
                if not isinstance(workspace, str) or len(workspace) > 4096 or '\x00' in workspace:
                    raise ValueError('invalid_workspace')
                command += ['--workspace', workspace]
            result = subprocess.run(command + ['status'], capture_output=True, text=True, timeout=10,
                                    env=self.environment())
            if result.returncode or len(result.stdout) > 65536: raise ValueError('environment_observation_failed')
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or data.get('protocol_version') != 1:
                raise ValueError('environment_protocol_mismatch')
            setup = self.command() + ['ui']
            if self.agent_kit: setup += ['--agent-kit-root', str(self.agent_kit)]
            data.update(availability='available', setup_command=shlex.join(setup + ['--open']))
            return data
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return dict(protocol_version=1, availability='unavailable', scope='not_observed',
                        reason='environment_core_unavailable', connections=[],
                        environment={'runtime': 'not_observed'})

    def open_services(self):
        with self.lock:
            if self.status().get('availability') != 'available':
                raise ValueError('environment_core_unavailable')
            if self.child is not None and self.child.poll() is None:
                return dict(status='already_running', scope='local_process_only')
            command = self.command() + ['ui', '--open']
            if self.agent_kit: command += ['--agent-kit-root', str(self.agent_kit)]
            self.child = subprocess.Popen(command, env=self.environment(), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return dict(status='launch_requested', scope='local_process_only')

    def close(self):
        with self.lock:
            if self.child is not None and self.child.poll() is None:
                self.child.send_signal(signal.SIGINT)
                try: self.child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.child.terminate()
                    self.child.wait(timeout=3)


locations=registered_locations()
bridge = EnvironmentBridge(os.environ.get('ENVIRONMENT_CORE_ROOT') or locations.get('core_root'),
    os.environ.get('DEV_ENVIRONMENT_ROOT') or locations.get('runtime_root'),
    os.environ.get('ENVIRONMENT_AGENT_KIT_ROOT') or locations.get('agent_kit_root'),
    None if os.environ.get('ENVIRONMENT_CORE_ROOT') else locations.get('core_digest'))
