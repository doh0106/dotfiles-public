#!/usr/bin/env python3
"""Desktop launcher lifecycle. POSIX backend: macOS, Linux and Windows through WSL."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

REPO = Path(__file__).resolve().parents[1]
ROOT = Path.home() / '.local/state/dotfiles-app' / hashlib.sha256(str(REPO).encode()).hexdigest()[:16]
STATE = ROOT / 'server.json'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def request(state, action='', timeout=2):
    port = state['port']
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid desktop port')
    url = f'http://127.0.0.1:{port}'
    req = urllib.request.Request(url + '/api/desktop' + action,
        data=b'' if action else None,
        headers={'Origin': url, 'X-Dotfiles-Instance': state['instance']})
    with OPENER.open(req, timeout=timeout) as response:
        result = json.load(response)
    if result.get('instance') != state['instance'] or result.get('repository') != str(REPO):
        raise ValueError('Desktop instance mismatch')
    return result

def current():
    try:
        state = json.loads(STATE.read_text())
        request(state)
        return state
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None

def serve(instance, idle_seconds):
    import dashboard
    from http.server import ThreadingHTTPServer
    last_seen = [time.monotonic()]
    class DesktopHandler(dashboard.Handler):
        def info(self):
            return dict(desktop=True,instance=instance,repository=str(REPO),
                        environment='WSL' if os.environ.get('WSL_DISTRO_NAME') else sys.platform)
        def do_GET(self):
            if self.path == '/api/desktop':
                if not self.valid_host():self.reply(403,{'error':'Invalid host'});return
                self.reply(200,self.info());return
            super().do_GET()
        def do_POST(self):
            if self.path in ('/api/desktop/ping','/api/desktop/stop'):
                origin=f'http://127.0.0.1:{self.server.server_port}'
                if not self.valid_host() or self.headers.get('Origin') != origin or self.headers.get('X-Dotfiles-Instance') != instance:
                    self.reply(403,{'error':'Invalid desktop request'});return
                last_seen[0]=time.monotonic()
                self.reply(200,self.info())
                if self.path.endswith('/stop'):
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            super().do_POST()
    server=ThreadingHTTPServer(('127.0.0.1',0),DesktopHandler)
    state=dict(port=server.server_port,instance=instance,pid=os.getpid(),repository=str(REPO))
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state));temporary.chmod(0o600);temporary.replace(STATE)
    finished=threading.Event()
    def idle_monitor():
        while not finished.wait(min(10,idle_seconds/3)):
            if time.monotonic()-last_seen[0]>idle_seconds:
                server.shutdown();return
    threading.Thread(target=idle_monitor,daemon=True).start()
    try:server.serve_forever(poll_interval=0.2)
    finally:
        finished.set();server.server_close();dashboard.bridge.close()
        try:
            if json.loads(STATE.read_text()).get('instance')==instance:STATE.unlink()
        except (OSError,ValueError):pass

def launch(idle_seconds):
    ROOT.mkdir(parents=True,exist_ok=True);ROOT.chmod(0o700)
    with (ROOT/'launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=current()
        if state:
            request(state,'/ping');return state
        instance=secrets.token_urlsafe(24)
        env=dict(os.environ)
        # A desktop process must not prolong a terminal's authentication session.
        for key in list(env):
            if key in ('BW_SESSION','SSH_AUTH_SOCK','SSH_AGENT_PID') or key.endswith(('_TOKEN','_PASSWORD','_SECRET','_API_KEY')):
                env.pop(key,None)
        env['PATH']=os.pathsep.join([str(Path.home()/'.local/bin'),'/opt/homebrew/bin','/usr/local/bin',env.get('PATH','')])
        logfile=ROOT/'server.log'
        # Bound logs to the latest launch. No request bodies or credentials are logged.
        with logfile.open('w') as log:
            logfile.chmod(0o600)
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'serve','--instance',instance,'--idle-seconds',str(idle_seconds)],
                env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,cwd=str(REPO))
        for _ in range(150):
            state=current()
            if state and state['instance']==instance:return state
            if child.poll() is not None:raise RuntimeError(f'대시보드를 시작하지 못했습니다. 로그: {logfile}')
            time.sleep(0.1)
        child.terminate()
        raise RuntimeError(f'대시보드 시작 시간이 초과되었습니다. 로그: {logfile}')

def open_window(url):
    if sys.platform=='darwin':
        for name in ('Google Chrome','Microsoft Edge'):
            app=Path('/Applications')/(name+'.app')
            if app.is_dir():
                subprocess.run(['open','-na',str(app),'--args','--app='+url],check=True);return
        subprocess.run(['open',url],check=True)
    else:webbrowser.open(url)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',nargs='?',choices=['launch','stop','serve'],default='launch')
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--instance')
    parser.add_argument('--idle-seconds',type=float,default=300)
    args=parser.parse_args()
    if args.action=='serve':
        if not args.instance:parser.error('serve requires instance')
        serve(args.instance,args.idle_seconds);return
    if args.action=='stop':
        state=current()
        if state:request(state,'/stop')
        print('Dotfiles 앱 서버를 종료했습니다.' if state else '실행 중인 앱 서버가 없습니다.');return
    state=launch(args.idle_seconds)
    url=f"http://127.0.0.1:{state['port']}/"
    print(url,flush=True)
    if not args.no_open:open_window(url)

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
