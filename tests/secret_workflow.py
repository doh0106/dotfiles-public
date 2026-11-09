#!/usr/bin/env python3
"""Isolated vault and real-agent workflow; no user's vault, key or auth is touched."""
import copy,json,os,re,subprocess,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import secret_workflow as flow
import dashboard
from http.server import ThreadingHTTPServer

class SecretWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='sw-',dir='/tmp');self.home=Path(self.temp.name);self.mocks=self.home/'bin';self.mocks.mkdir()
  self.env=patch.dict(os.environ,dict(HOME=str(self.home),PATH=str(self.mocks)+os.pathsep+os.environ['PATH']));self.env.start()
  for name in ('BW_SESSION','SSH_AUTH_SOCK','SSH_AGENT_PID'):os.environ.pop(name,None)
  self.paths=patch.multiple(cfg,DATA=self.home/'.config/dotfiles/dashboard',SETTINGS=self.home/'.config/dotfiles/dashboard/settings.json');self.paths.start()
  subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.home/'fixture')],check=True)
  self.private=(self.home/'fixture').read_text();self.public=' '.join((self.home/'fixture.pub').read_text().split()[:2]);self.token='synthetic-token-never-in-http'
  store=self.home/'fixture-vault.json';store.write_text(json.dumps(dict(private=self.private,public=self.public,token=self.token)))
  script='''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
v=json.loads((Path.home()/'fixture-vault.json').read_text());a=sys.argv[1:]
if a[0]=='status': print(json.dumps({'status':'unlocked' if os.environ.get('BW_SESSION')=='synthetic-session-123456' else 'locked'}))
elif a[:2]==['list','items']:
 print(json.dumps([{'id':'key-1234','name':'Personal SSH key','type':5,'sshKey':{'privateKey':v['private'],'publicKey':v['public']}},{'id':'note-1234','name':'Legacy SSH note','type':2,'notes':v['private']},{'id':'token-1234','name':'API token','type':2,'notes':v['token']},{'id':'login-1234','name':'Service login','type':1,'login':{'password':v['token']}},{'id':'deleted-1234','name':'Deleted','type':5,'deletedDate':'yesterday'}]))
elif a[:2]==['get','item']:print(json.dumps({'sshKey':{'privateKey':v['private'],'publicKey':v['public']}}))
elif a[:2]==['get','notes']:print(v['private'] if a[2]=='note-1234' else v['token'])
elif a[:2]==['get','password']:print(v['token'])
else:sys.exit(9)
'''
  bw=self.mocks/'bw';bw.write_text(script);bw.chmod(0o755)
  self.workflow=flow.Workflow('http://127.0.0.1:12345')
 def tearDown(self):
  self.workflow.close();self.paths.stop();self.env.stop();self.temp.cleanup()
 def connect(self):
  handoff=self.workflow.connect();ticket=self.workflow.ticket
  self.assertNotIn('BW_SESSION',handoff['command']);self.workflow.attach(ticket,'synthetic-session-123456')
 def prepared(self):
  self.connect();self.workflow.search('ssh','ssh-key');key=self.workflow.prepare('key-1234');return self.workflow.save_public(key['id'],str(self.home/'keys/personal.pub'))
 def test_connection_is_one_time_expiring_and_not_persisted(self):
  self.connect();self.assertTrue(self.workflow.status()['connected'])
  with self.assertRaises(ValueError):self.workflow.attach('already-used','synthetic-session-123456')
  self.workflow.expires=0;self.assertFalse(self.workflow.status()['connected']);self.assertIsNone(self.workflow.session)
  for path in self.home.rglob('*'):
   if path.is_file() and path.name!='bw':self.assertNotIn(b'synthetic-session-123456',path.read_bytes())
 def test_metadata_never_contains_secret_bodies_and_lookup_requires_selection(self):
  self.connect();result=self.workflow.search('ssh','ssh-key');text=json.dumps(result)
  self.assertNotIn('PRIVATE KEY',text);self.assertNotIn(self.token,text);self.assertNotIn('deleted-1234',text)
  self.assertNotIn('login-1234',[item['id'] for item in result['items']])
  with self.assertRaises(ValueError):self.workflow.prepare('not-selected')
 def test_public_derivation_writes_only_public_file_and_never_overwrites(self):
  key=self.prepared();path=Path(key['path']);self.assertEqual(path.read_text().strip(),self.public)
  self.workflow.save_public(key['id'],str(path))
  other=self.home/'keys/different.pub';other.write_text('ssh-ed25519 OTHER')
  with self.assertRaises(ValueError):self.workflow.save_public(key['id'],str(other))
  self.assertEqual(other.read_text(),'ssh-ed25519 OTHER')
  alias=self.home/'keys/link.pub';alias.symlink_to(path)
  with self.assertRaises(ValueError):self.workflow.save_public(key['id'],str(alias))
  with self.assertRaises(ValueError):self.workflow.save_public(key['id'],'/tmp/outside.pub')
 def test_supply_expiry_policy_and_cleanup_use_a_real_isolated_agent(self):
  key=self.prepared();result=self.workflow.supply(key['id'],60)
  self.assertTrue(result['added']);self.assertTrue(result['dedicated_agent']);self.assertEqual(result['lifetime'],60)
  listed=subprocess.run(['ssh-add','-L'],env=self.workflow.agent_env,capture_output=True,text=True);self.assertIn(self.public,listed.stdout)
  repeated=self.workflow.supply(key['id'],120);self.assertFalse(repeated['added']);self.assertIsNone(repeated['lifetime'])
  self.workflow.cleanup();empty=subprocess.run(['ssh-add','-l'],env=self.workflow.agent_env,capture_output=True,text=True);self.assertEqual(empty.returncode,1)
 def test_normal_restart_reuses_the_same_dedicated_socket_address(self):
  key=self.prepared();first=self.workflow.supply(key['id'],60)['agent_socket'];self.workflow.close()
  replacement=flow.Workflow('http://127.0.0.1:12345')
  try:
   replacement.connect();replacement.attach(replacement.ticket,'synthetic-session-123456');replacement.search('ssh','ssh-key');prepared=replacement.prepare('key-1234');saved=replacement.save_public(prepared['id'],key['path']);second=replacement.supply(saved['id'],60)['agent_socket'];self.assertEqual(first,second)
  finally:replacement.close()
 def test_shared_agent_preexisting_keys_are_preserved(self):
  started=subprocess.run(['ssh-agent','-a',str(self.home/'shared.sock'),'-s'],capture_output=True,text=True,check=True)
  socket=re.search(r'SSH_AUTH_SOCK=([^;]+)',started.stdout).group(1);pid=re.search(r'SSH_AGENT_PID=(\d+)',started.stdout).group(1)
  env=dict(os.environ,SSH_AUTH_SOCK=socket,SSH_AGENT_PID=pid)
  try:
   subprocess.run(['ssh-add',str(self.home/'fixture')],env=env,capture_output=True,check=True)
   with patch.dict(os.environ,{'SSH_AUTH_SOCK':socket,'SSH_AGENT_PID':pid}):
    key=self.prepared();result=self.workflow.supply(key['id'],60);self.assertFalse(result['added']);self.assertFalse(result['dedicated_agent']);self.workflow.cleanup()
   listed=subprocess.run(['ssh-add','-L'],env=env,capture_output=True,text=True);self.assertIn(self.public,listed.stdout)
  finally:subprocess.run(['ssh-agent','-k'],env=env,capture_output=True)
 def test_private_notes_and_token_purposes_cannot_be_confused(self):
  self.connect();self.workflow.search('token','token');result=self.workflow.check_token('token-1234')
  self.assertTrue(result['ready']);self.assertNotIn(self.token,json.dumps(result))
  with self.assertRaises(ValueError):self.workflow.check_token('note-1234')
  self.assertNotIn('key-1234',self.workflow.items)
 def test_dispatch_and_policy_validation(self):
  self.connect()
  for request in [dict(action='search',query='',purpose='token'),dict(action='status',extra=True),dict(action='dump'),dict(action='supply_key',id='unknown',lifetime=0)]:
   with self.assertRaises(ValueError):self.workflow.dispatch(request)
 def test_dedicated_socket_is_used_only_by_explicit_key_configs(self):
  state=cfg.defaults();state['profiles']=[];c=cfg.new_connection('','new');c.update(enabled=True,publicKey=str(self.home/'fixture.pub'),agentSocket='/tmp/example/agent.sock');state['connections']=[c]
  files=cfg.compile(state);self.assertIn('IdentityAgent "/tmp/example/agent.sock"',files['ssh-connection-new.config'])
  c['sshMode']='system';self.assertNotIn('ssh-connection-new.config',cfg.compile(state))
 def test_generic_token_supply_is_child_scoped_and_has_no_vault_session(self):
  cfg.DATA.mkdir(parents=True);state=cfg.defaults();state['credentials']=[dict(id='my-token',purpose='token',source='bitwarden',kind='note',item='token-1234',variable='',helper='cache',username='',deliveryVariable='SERVICE_TOKEN')];cfg.SETTINGS.write_text(json.dumps(state))
  program=self.home/'client.py';program.write_text('import os,json;print(json.dumps(dict(selected=os.environ.get("SERVICE_TOKEN")=="synthetic-token-never-in-http",vault="BW_SESSION" in os.environ,other="GH_TOKEN" in os.environ)))')
  result=subprocess.run([sys.executable,str(cfg.REPO/'bin/secret_supply.py'),'--reference','my-token','--',sys.executable,str(program)],env=dict(os.environ,BW_SESSION='synthetic-session-123456',GH_TOKEN='unrelated'),capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),dict(selected=True,vault=False,other=False));self.assertNotIn(self.token,result.stdout+result.stderr)
 def test_managed_agent_cli_checks_the_supplied_socket_without_vault_lookup(self):
  import auth,io,contextlib,runbook
  key=self.prepared();supplied=self.workflow.supply(key['id'],60)
  state=cfg.defaults();state['profiles']=[];state['credentials']=[dict(id='key',purpose='ssh-key',source='bitwarden',kind='sshkey',item='key-1234',variable='',helper='cache',username='')]
  c=cfg.new_connection('','example');c.update(enabled=True,credential='key',publicKey=key['path'],agentSocket=supplied['agent_socket']);state['connections']=[c]
  runtime=json.loads(cfg.compile(state)['profiles.json'])
  with patch('auth.configuration',return_value=runtime),patch('auth.fetch',side_effect=AssertionError('must not refetch')):
   for action,expected in [('prepare','ssh-managed'),('needs-vault','none'),('load','')]:
    output=io.StringIO()
    with patch.object(sys,'argv',['auth.py',action,'--connection','example']),contextlib.redirect_stdout(output):auth.main()
    self.assertEqual(output.getvalue().strip(),expected)
  steps=runbook.build(state,[],cfg.REPO,cfg.DATA);self.assertNotIn('vault',[step['id'] for step in steps]);self.assertIn('managed-agent',[step['id'] for step in steps])
 def test_first_login_uses_api_key_environment_and_clears_it_before_work_shell(self):
  import secret_session,io,contextlib
  self.workflow.connect();request=Path(self.workflow.launch_dir.name)/'request.json';calls=[]
  def capture(args,env):
   calls.append((args,dict(env)))
   if args[1]=='status':return '{"status":"unauthenticated"}'
   if args[1]=='login':return '{}'
   return 'synthetic-session-123456'
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,*args):return b'{"connected":true}'
  output=io.StringIO()
  with patch('secret_session.capture',side_effect=capture),patch('builtins.input',return_value='synthetic-client-id'),patch('secret_session.getpass.getpass',side_effect=['synthetic-client-secret','synthetic-master']),patch('secret_session.urllib.request.urlopen',return_value=Response()),patch('secret_session.os.execve') as execute,contextlib.redirect_stdout(output):secret_session.connect(str(request))
  self.assertEqual(calls[1][0],['bw','login','--apikey','--nointeraction']);self.assertEqual(calls[1][1]['BW_CLIENTSECRET'],'synthetic-client-secret')
  self.assertNotIn('BW_CLIENTSECRET',execute.call_args.args[2]);self.assertNotIn('DOTFILES_VAULT_PASSWORD',execute.call_args.args[2]);self.assertNotIn('synthetic-master',output.getvalue());self.assertNotIn('synthetic-client-secret',output.getvalue())
 def test_live_readiness_survives_vault_disconnect_and_detects_agent_cleanup(self):
  key=self.prepared();supplied=self.workflow.supply(key['id'],60)
  state=cfg.defaults();state['profiles']=[];c=cfg.new_connection('','saved-key');c.update(enabled=True,publicKey=key['path'],agentSocket=supplied['agent_socket']);state['connections']=[c];cfg.DATA.mkdir(parents=True,exist_ok=True);cfg.SETTINGS.write_text(json.dumps(state))
  self.workflow.forget();status=self.workflow.status();self.assertFalse(status['connected']);self.assertEqual(status['keys'][0]['state'],'ready')
  self.workflow.cleanup();self.assertEqual(self.workflow.status()['keys'][0]['state'],'not_loaded')
 def test_prepare_saved_reuses_matching_public_file_without_rewriting(self):
  key=self.prepared();path=Path(key['path']);before=path.stat().st_mtime_ns
  state=cfg.defaults();state['profiles']=[];state['credentials']=[dict(id='key',purpose='ssh-key',source='bitwarden',kind='sshkey',item='key-1234',variable='',helper='cache',username='')]
  c=cfg.new_connection('','example');c.update(enabled=True,credential='key',publicKey=key['path']);state['connections']=[c];cfg.DATA.mkdir(parents=True,exist_ok=True);cfg.SETTINGS.write_text(json.dumps(state))
  self.workflow.forget();self.connect();prepared=self.workflow.prepare_saved(c['id']);self.assertTrue(prepared['saved']);self.assertEqual(prepared['path'],str(path));self.assertEqual(path.stat().st_mtime_ns,before)
 def test_legacy_manifest_metadata_is_deduplicated_and_never_executes_actions(self):
  import legacy_secrets
  manifest=self.home/'secrets.json';rows=[dict(bw_name='key-1234',bw_type='sshkey',action='ssh-add'),dict(bw_name='key-1234',bw_type='sshkey',action='ssh-add'),dict(bw_name='do-not-run',bw_type='note',action='eval-env',value='SECRET-BODY'),dict(bw_name='not-private',bw_type='sshkey',action='ssh-add',field='public')];manifest.write_text(json.dumps(dict(secrets=rows)))
  with patch.dict(os.environ,DOTFILES_SECRETS_MANIFEST=str(manifest)),patch.object(self.workflow,'run',side_effect=AssertionError('metadata must not run commands')):
   listed=legacy_secrets.registrations();self.assertEqual(len(listed['items']),1);self.assertNotIn('SECRET-BODY',json.dumps(listed));self.assertNotIn('do-not-run',json.dumps(listed));self.assertTrue(listed['warnings']);self.assertEqual(json.loads(manifest.read_text())['secrets'],rows)
 def test_legacy_key_preparation_reuses_exact_existing_public_key_only(self):
  import legacy_secrets
  manifest=self.home/'secrets.json';manifest.write_text(json.dumps(dict(secrets=[dict(bw_name='key-1234',bw_type='sshkey',action='ssh-add')])))
  self.connect();before=(self.home/'fixture.pub').stat().st_mtime_ns
  candidates=[dict(id='original',name='original-alias',path=str(self.home/'fixture.pub'))]
  with patch.dict(os.environ,DOTFILES_SECRETS_MANIFEST=str(manifest)),patch.object(self.workflow,'key_status',return_value=candidates):
   ident=legacy_secrets.registrations()['items'][0]['id'];result=self.workflow.dispatch(dict(action='prepare_registered',registration=ident));self.assertTrue(result['saved']);self.assertEqual(result['path'],str(self.home/'fixture.pub'));self.assertEqual(result['existing_connections'],['original-alias']);self.assertEqual((self.home/'fixture.pub').stat().st_mtime_ns,before)
   (self.home/'fixture.pub').write_text('ssh-ed25519 DIFFERENT');result=self.workflow.prepare_registered(ident);self.assertFalse(result['saved']);self.assertEqual(result['existing_connections'],[])
  with self.assertRaises(ValueError):self.workflow.prepare_registered('not-in-manifest')
 def test_batch_supply_merges_registrations_and_preserves_existing_agent_keys(self):
  manifest=self.home/'secrets.json';manifest.write_text(json.dumps(dict(secrets=[dict(bw_name='key-1234',bw_type='sshkey',action='ssh-add'),dict(bw_name='broken',bw_type='note',action='ssh-add')])))
  state=cfg.defaults();state['credentials']=[dict(id='saved-key',purpose='ssh-key',source='bitwarden',kind='sshkey',item='key-1234',variable='',helper='cache',username='')];cfg.DATA.mkdir(parents=True,exist_ok=True);cfg.SETTINGS.write_text(json.dumps(state))
  self.connect()
  with patch.dict(os.environ,DOTFILES_SECRETS_MANIFEST=str(manifest)):
   self.assertEqual(len(self.workflow.registered_keys()),2)
   first=self.workflow.dispatch(dict(action='supply_all',lifetime=60));self.assertEqual([r['state'] for r in first['results']],['added','failed']);self.assertNotIn(self.token,json.dumps(first))
   deadline=dict(self.workflow.added);again=self.workflow.supply_all(120);self.assertEqual(again['results'][0]['state'],'reused');self.assertEqual(deadline,self.workflow.added)
   self.assertFalse((self.home/'.ssh').exists());self.assertFalse((self.home/'keys').exists());self.assertEqual(json.loads(cfg.SETTINGS.read_text()),state)
  self.workflow.cleanup();self.assertEqual(subprocess.run(['ssh-add','-l'],env=self.workflow.agent_env,capture_output=True).returncode,1)
 def test_dashboard_connection_lifetime_is_separate_from_key_policy(self):
  self.assertEqual(self.workflow.connection_lifetime(),15);self.workflow.set_connection_lifetime(5);self.assertEqual(self.workflow.connection_lifetime(),5)
  before=time.monotonic();self.connect();self.assertTrue(before+299<=self.workflow.expires<=time.monotonic()+300)
  expiry=self.workflow.expires;self.workflow.set_connection_lifetime(30);self.assertEqual(expiry,self.workflow.expires);self.assertEqual(cfg.defaults()['session']['keyLifetime'],3600)
  with self.assertRaises(ValueError):self.workflow.set_connection_lifetime(0)
  self.assertNotIn('synthetic-session', (cfg.DATA/'vault-preferences.json').read_text())
 def test_environment_supply_accepts_api_key_and_strips_other_managed_variables(self):
  cfg.DATA.mkdir(parents=True);state=cfg.defaults();base=dict(purpose='token',source='bitwarden',kind='note',item='token-1234',variable='',helper='cache',username='');state['credentials']=[dict(base,id='api-key',deliveryVariable='API_KEY'),dict(base,id='other',deliveryVariable='OTHER_SECRET')];cfg.SETTINGS.write_text(json.dumps(state));cfg.validate(state)
  program=self.home/'client.py';program.write_text('import os,json;print(json.dumps(dict(selected=os.environ.get("API_KEY")=="synthetic-token-never-in-http",other="OTHER_SECRET" in os.environ,vault="BW_SESSION" in os.environ)))')
  result=subprocess.run([sys.executable,str(cfg.REPO/'bin/secret_supply.py'),'--reference','api-key','--',sys.executable,str(program)],env=dict(os.environ,BW_SESSION='synthetic-session-123456',OTHER_SECRET='must-not-inherit'),capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),dict(selected=True,other=False,vault=False))
  for variable in ['PATH','BW_SESSION','SSH_AUTH_SOCK','LD_PRELOAD','NODE_OPTIONS']:
   state['credentials'][0]['deliveryVariable']=variable
   with self.assertRaises(ValueError):cfg.validate(state)
 def test_ui_unlock_keeps_passwords_out_of_arguments_files_and_response(self):
  calls=[]
  def run(args,**kw):
   calls.append((args,dict(kw.get('env',{}))))
   if args[:2]==['bw','status']:return subprocess.CompletedProcess(args,0,json.dumps(dict(status='unlocked' if kw.get('env',{}).get('BW_SESSION') else 'locked')),'')
   if args[:2]==['bw','unlock']:return subprocess.CompletedProcess(args,0,'synthetic-session-123456','')
   return subprocess.CompletedProcess(args,0,'','')
  with patch.object(self.workflow,'run',side_effect=run):result=self.workflow.unlock_ui('synthetic-master')
  self.assertTrue(result['connected']);self.assertNotIn('synthetic-master',json.dumps(result));self.assertNotIn('synthetic-master',json.dumps([args for args,env in calls]));self.assertEqual(next(env for args,env in calls if args[:2]==['bw','unlock'])['DOTFILES_VAULT_PASSWORD'],'synthetic-master')
  self.assertFalse(cfg.DATA.exists())
 def test_ui_first_login_uses_environment_and_does_not_forward_api_secret_to_unlock(self):
  calls=[]
  def run(args,**kw):
   env=dict(kw.get('env',{}));calls.append((args,env))
   if args[:2]==['bw','status']:return subprocess.CompletedProcess(args,0,json.dumps(dict(status='unlocked' if env.get('BW_SESSION') else 'unauthenticated')),'')
   return subprocess.CompletedProcess(args,0,'synthetic-session-123456' if args[:2]==['bw','unlock'] else '','')
  with patch.object(self.workflow,'run',side_effect=run):self.workflow.unlock_ui('synthetic-master','synthetic-client-id','synthetic-api-secret')
  login=next(env for args,env in calls if args[:2]==['bw','login']);unlock=next(env for args,env in calls if args[:2]==['bw','unlock'])
  self.assertEqual(login['BW_CLIENTSECRET'],'synthetic-api-secret');self.assertNotIn('BW_CLIENTSECRET',unlock);self.assertNotIn('synthetic-api-secret',json.dumps([args for args,env in calls]))
 def test_saved_github_install_token_is_not_a_global_credential_change(self):
  self.connect();cfg.DATA.mkdir(parents=True,exist_ok=True);state=cfg.defaults();state['credentials']=[dict(id='github-install',purpose='token',source='bitwarden',kind='note',item='token-1234',variable='',helper='cache',username='',deliveryVariable='GITHUB_TOKEN')];cfg.SETTINGS.write_text(json.dumps(state));before=cfg.SETTINGS.read_bytes()
  result=self.workflow.github_install_environment();self.assertTrue(result['GIT_CONFIG_VALUE_0'].startswith('Authorization: Basic '));self.assertEqual(cfg.SETTINGS.read_bytes(),before);self.assertNotIn(self.token,json.dumps(self.workflow.status()));self.assertNotIn('GIT_CONFIG_VALUE_0',os.environ)
  self.workflow.forget()
  with self.assertRaises(ValueError):self.workflow.github_install_environment()
 def test_ui_unlock_failure_never_echoes_provider_output(self):
  def run(args,**kw):return subprocess.CompletedProcess(args,0,json.dumps(dict(status='locked')),'') if args[:2]==['bw','status'] else subprocess.CompletedProcess(args,1,'SENSITIVE-PROVIDER-OUTPUT','SENSITIVE-PROVIDER-OUTPUT')
  with patch.object(self.workflow,'run',side_effect=run):
   with self.assertRaises(ValueError) as error:self.workflow.unlock_ui('synthetic-master')
  self.assertNotIn('SENSITIVE',str(error.exception));self.assertIsNone(self.workflow.session)
 def test_terminal_handoff_keeps_passwords_and_session_out_of_output(self):
  import secret_session,io,contextlib
  handoff=self.workflow.connect();request=Path(self.workflow.launch_dir.name)/'request.json'
  calls=[]
  def capture(args,env):
   calls.append((args,dict(env)))
   if args[1]=='status':return '{"status":"locked"}'
   return 'synthetic-session-123456'
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,*args):return b'{"connected":true}'
  output=io.StringIO()
  with patch('secret_session.capture',side_effect=capture),patch('secret_session.getpass.getpass',return_value='synthetic-master'),patch('secret_session.urllib.request.urlopen',return_value=Response()),patch('secret_session.os.execve') as execute,contextlib.redirect_stdout(output):
   secret_session.connect(str(request))
  self.assertNotIn('synthetic-master',output.getvalue());self.assertNotIn('synthetic-session-123456',output.getvalue());self.assertNotIn('BW_SESSION',os.environ)
  self.assertEqual(execute.call_args.args[2]['BW_SESSION'],'synthetic-session-123456')
  self.assertNotIn('DOTFILES_VAULT_PASSWORD',execute.call_args.args[2]);self.assertFalse(request.exists())
  self.assertNotIn('synthetic-master',' '.join(calls[1][0]))
 def test_http_csrf_and_session_error_never_echo_secrets(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),dashboard.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
  def post(path,data,include_origin=True):
   return urllib.request.urlopen(urllib.request.Request(origin+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json',**({'Origin':origin} if include_origin else {})}))
  try:
   with self.assertRaises(urllib.error.HTTPError) as caught:post('/api/secrets',{'action':'status'},False)
   self.assertEqual(caught.exception.code,403);caught.exception.close()
   with post('/api/secrets',{'action':'status'}) as response:self.assertFalse(json.load(response)['connected'])
   with self.assertRaises(urllib.error.HTTPError) as caught:post('/api/secret-session',{'ticket':'bad','session':self.token})
   self.assertNotIn(self.token,caught.exception.read().decode());caught.exception.close()
   server.design_preview=True
   with self.assertRaises(urllib.error.HTTPError) as caught:post('/api/secrets',{'action':'connect','launch':False})
   self.assertEqual(caught.exception.code,403);caught.exception.close()
  finally:
   if getattr(server,'secret_workflow',None):server.secret_workflow.close()
   server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main(verbosity=2)
