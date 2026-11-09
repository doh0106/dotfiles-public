'use strict';
// Browser state contains metadata and public keys only; vault sessions stay in the broker.
const secretFlow={status:null,statusAttempted:false,busy:false,error:'',handoff:null,key:null,token:null,deliveryVariable:'SERVICE_TOKEN',programReference:'',searches:{'ssh-key':{query:'',items:[]},token:{query:'',items:[]}}};
async function workflowRequest(request){const response=await fetch('/api/secrets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const data=await response.json();if(!response.ok)throw Error(data.error);return data;}
function renderSecretFlow(){if(view==='key-supply')renderSecretSshWorkflow();else if(view==='secret-tokens')renderSecretTokenWorkflow();else if(view==='providers')renderBitwardenSettings();else if(view==='overview')renderControlCenter();attachDomainNavigation();}
async function flowAction(request,done=()=>{}){
 if(secretFlow.busy)return;secretFlow.busy=true;secretFlow.error='';renderSecretFlow();
 try{const previous=secretFlow.status?.generation,result=await workflowRequest(request);done(result);secretFlow.status=request.action==='status'?result:await workflowRequest({action:'status'});if(previous&&previous!==secretFlow.status.generation){secretFlow.key=null;secretFlow.token=null;for(const search of Object.values(secretFlow.searches))search.items=[]}}
 catch(error){secretFlow.error=error.message}
 finally{secretFlow.busy=false;renderSecretFlow()}
}
function flowButton(title,request,done,disabled=false){const b=button(title,()=>flowAction(typeof request==='function'?request():request,done),'btn');b.disabled=secretFlow.busy||disabled||snapshot.design_preview;return b;}
function flowStep(root,number,title,text){const box=groupBox(title,root);if(text)box.append(el('p',text,'tool-state'));return box;}
function supplyHeader(root){
 const bar=el('div',undefined,'control-statusbar'),status=secretFlow.status;
 bar.append(badge(status?.connected?'Bitwarden 연결됨':'Bitwarden 연결 필요',status?.connected?'green':'amber'));
 if(!status?.connected&&view!=='providers')bar.append(button('연결하기',()=>navigate('providers'),'quiet'));
 const refresh=flowButton('↻',{action:'status'});refresh.setAttribute('aria-label','Bitwarden 상태 새로고침');bar.append(refresh);root.append(bar);
 if(secretFlow.error){const error=el('p',secretFlow.error,'notice');error.setAttribute('role','alert');root.append(error)}
 if(!status&&!secretFlow.statusAttempted&&!secretFlow.busy&&!snapshot.design_preview){secretFlow.statusAttempted=true;queueMicrotask(()=>flowAction({action:'status'}))}
}
function flowVault(root){
 supplyHeader(root);
 if(secretFlow.status?.connected){root.append(el('p','Bitwarden에 연결되어 있습니다. 필요한 값은 공급 작업에서 가져옵니다.','hint'));const more=el('details',undefined,'control-more');more.append(el('summary','연결 관리'),flowButton('대시보드 연결 해제',{action:'disconnect'}));root.append(more);instructionLink(root,'항목 생성·편집은 Bitwarden에서','https://vault.bitwarden.com/');return}
 const form=el('form',undefined,'vault-connect-form');root.append(form);
 form.append(el('p','기존 CLI 계정을 사용해 잠금을 해제합니다. 보관 항목을 만들거나 수정하는 작업은 Bitwarden에서 진행하세요.','hint'));
 const password=field(form,'마스터 비밀번호','',null,()=>{},'vault-master','password');password.autocomplete='current-password';
 const first=el('details');first.append(el('summary','처음 CLI에 로그인할 때 · 개인 API 키'));form.append(first);
 const client=field(first,'client_id','',null,()=>{},'vault-client-id');client.placeholder='user.…';client.autocomplete='off';
 const secret=field(first,'client_secret','',null,()=>{},'vault-client-secret','password');secret.autocomplete='off';
 instructionLink(first,'Bitwarden에서 개인 API 키 확인','https://bitwarden.com/help/personal-api-key/');
 const submit=button(secretFlow.status?.connected?'다시 연결':'잠금 해제하고 연결',()=>{},'btn primary');submit.type='submit';submit.disabled=secretFlow.busy||snapshot.design_preview;form.append(submit);
 form.onsubmit=event=>{event.preventDefault();if(secretFlow.busy||snapshot.design_preview)return;const request={action:'unlock_ui',password:password.value,client_id:client.value,client_secret:secret.value};password.value=client.value=secret.value='';flowAction(request).finally(()=>{request.password=request.client_id=request.client_secret=''})};
 const more=el('details',undefined,'control-more');more.append(el('summary','연결 옵션 · 터미널 연결'));root.append(more);flowTerminalVault(more);
 instructionLink(root,'항목 생성·편집은 Bitwarden에서','https://vault.bitwarden.com/');
}
function flowTerminalVault(root){
 const box=flowStep(root,'','Bitwarden 연결','로그인 정보는 터미널에서 입력합니다. 대시보드 연결 유지 시간은 아래에서 설정합니다. 세션 값은 브라우저나 파일에 저장하지 않습니다.');
 const status=secretFlow.status;
 box.append(badge(status?.connected?'저장소 연결됨 · '+Math.ceil(status.expires_in/60)+'분 남음':status?.pending?'터미널 연결 대기 중':'저장소 연결 필요',status?.connected?'green':'amber'));
 if(status&&['ssh-add','ssh-keygen','ssh-agent'].some(tool=>!status.installed[tool])){box.append(el('p','SSH 키 준비에는 OpenSSH 도구가 필요합니다. 설치 후 상태를 갱신하세요.','hint'));instructionLink(box,'OpenSSH 설치 안내','https://www.openssh.com/portable.html');}
 if(status&&!status.installed.bw){box.append(el('p','Bitwarden CLI가 없습니다. 설치 후 연결 상태를 다시 확인하세요.','hint'));instructionLink(box,'Bitwarden CLI 설치 안내','https://bitwarden.com/help/cli/');}
 const terminals=status?.terminals||[];if(terminals.length)field(box,'기본 터미널 앱',status.default_terminal||'',[['','처음 사용할 터미널을 선택하세요'],...terminals.map(item=>[item.id,item.title])],value=>{if(value)flowAction({action:'set_terminal',terminal:value})},'vault-default-terminal');
 box.append(flowButton('로그인 명령 준비 · 실행하지 않음',{action:'connect',launch:Boolean(status?.terminals?.length)},result=>{secretFlow.handoff=result;secretFlow.key=null;secretFlow.token=null},Boolean(terminals.length&&!status.default_terminal)),flowButton('연결 상태 갱신',{action:'status'}),flowButton('대시보드 연결 해제',{action:'disconnect'},()=>{secretFlow.key=null;secretFlow.token=null;for(const search of Object.values(secretFlow.searches))search.items=[]},!status?.connected));
 if(secretFlow.handoff){box.append(el('p',secretFlow.handoff.handoff_mode==='input'?'터미널에 명령을 입력해 두었습니다. 내용을 확인하고 직접 Enter를 눌러 실행하세요.':secretFlow.handoff.handoff_mode==='clipboard'?'명령을 복사하고 선택한 앱을 열었습니다. 새 터미널 프롬프트에 붙여넣고 직접 Enter를 누르세요.':'아래 명령을 터미널에 붙여넣고 직접 실행하세요.','hint'),el('pre',secretFlow.handoff.command,'long-pre'));}
 instructionLink(box,'첫 CLI 로그인용 개인 API 키 찾기','https://bitwarden.com/help/personal-api-key/');
 box.append(el('p','첫 로그인은 계정의 개인 API 키로 CLI에 로그인한 뒤 마스터 비밀번호로 잠금을 해제합니다. 기존 CLI 계정은 바꾸지 않습니다. 연결한 터미널은 작업용 셸로 유지됩니다.','hint'));
 if(secretFlow.error){const error=el('p',secretFlow.error,'notice');error.setAttribute('role','alert');box.append(error);}
 if(!status&&!secretFlow.statusAttempted&&!secretFlow.busy&&!snapshot.design_preview){secretFlow.statusAttempted=true;queueMicrotask(()=>flowAction({action:'status'}));}
 return box;
}
function flowSearch(root,purpose){
 const search=secretFlow.searches[purpose],box=flowStep(root,'','저장소 항목 검색·선택','이름으로 검색합니다. 목록에는 이름·항목 종류만 표시하며 개인키·값 본문은 표시하지 않습니다.');
 const input=field(box,'검색할 항목 이름',search.query,null,value=>{search.query=value},'vault-item-search');input.placeholder=purpose==='ssh-key'?'예: github ssh key':'예: github token 또는 api key';
 const lookup=()=>({action:'search',query:search.query,purpose});
 box.append(flowButton('항목 검색',lookup,result=>{search.items=result.items},!secretFlow.status?.connected));
 if(search.items.length){const list=el('div',undefined,'vault-results');for(const item of search.items){const row=el('article',undefined,'vault-item');row.append(el('strong',item.name),el('p',({note:'Secure Note',sshkey:'SSH Key',login:'Login'})[item.kind]+' · 항목 ID '+item.id,'hint'));
  row.append(flowButton(purpose==='ssh-key'?'키 확인':'값 형식 확인',{action:purpose==='ssh-key'?'prepare_public':'check_token',item:item.id},result=>{if(purpose==='ssh-key')secretFlow.key=result;else secretFlow.token=result},!secretFlow.status?.connected));list.append(row)}box.append(list);}
 else box.append(el('p','2자 이상 검색어를 입력하세요. SSH 키는 SSH Key·Secure Note, 토큰은 Secure Note·Login 항목을 선택할 수 있습니다.','hint'));
}
function flowReference(item,purpose,username=null){
 let ref=draft.credentials.find(ref=>ref.source==='bitwarden'&&ref.item===item.item&&ref.kind===item.kind&&secretPurpose(ref)===purpose&&(username===null||ref.username===username));
 if(!ref){ref=makeCredential(uniqueId((purpose==='ssh-key'?'ssh-key-':'token-')+(item.item.toLowerCase().replace(/[^a-z0-9-]/g,'-').slice(0,40)||'item'),draft.credentials));Object.assign(ref,{purpose,kind:item.kind,item:item.item,username:username||''});draft.credentials.push(ref)}ref.purpose=purpose;return ref;
}
function flowConnectionRecords(kind){return draft.connections.filter(c=>kind==='ssh'?c.method==='ssh':c.kind==='git'&&(c.method==='https'||c.api.enabled)).map(c=>({id:c.id,title:c.name,lines:connectionLines(c)}));}

function renderSecretSshWorkflow(){
 const root=$('page-body');root.replaceChildren();supplyHeader(root);const layout=el('div',undefined,'control-layout'),main=el('section'),aside=el('aside');layout.append(main,aside);root.append(layout);
 const box=groupBox('등록된 SSH 키 한 번에 공급',main),rows=secretFlow.status?.registered_keys||[];
 box.append(el('p','bws처럼 저장된 목록의 키를 모두 가져와 SSH agent에 넣습니다. 기존 bws 등록도 자동으로 포함하며 접속 설정은 바꾸지 않습니다.','hint'));
 const options=el('details',undefined,'control-more');options.append(el('summary','공급 옵션 · 키 유지 시간'));box.append(options);
 field(options,'새로 공급하는 키 유지 시간 · 초',draft.session.keyLifetime,null,value=>{draft.session.keyLifetime=Number(value);mark()},'key-lifetime','number');
 options.append(el('p','60~86400초. 이미 agent에 있는 같은 키는 재사용하고 기존 유지 시간은 바꾸지 않습니다. 목록·시간의 변경은 변경 검토에서 저장합니다.','hint'));
 const supply=flowButton('등록된 키 모두 공급',()=>({action:'supply_all',lifetime:draft.session.keyLifetime}),()=>{},!rows.length||!secretFlow.status?.connected);supply.classList.add('primary');box.append(supply);
 const result=secretFlow.status?.last_supply;
 if(result){const report=groupBox('최근 공급 결과',main);for(const row of result.results)report.append(el('p',row.item+' · '+({added:'공급 완료',reused:'이미 agent에 있음 · 재사용',failed:'공급 실패'})[row.state],row.state==='failed'?'notice':'tool-state'));
  report.append(el('p','agent 소켓: '+result.agent_socket,'hint'));
  if(result.dedicated_agent)report.append(el('p','기존 agent가 없어 별도 agent를 사용했습니다. 이 agent를 쓸 터미널에서 아래 명령을 실행하세요. SSH 연결 설정은 자동 변경하지 않습니다.','hint'),el('pre','export SSH_AUTH_SOCK='+"'"+result.agent_socket.replaceAll("'","'\"'\"'")+"'",'long-pre'));
 }
 const list=groupBox('등록된 키 · '+rows.length+'개',aside);
 for(const row of rows){const card=el('article',undefined,'auth-link-card');card.append(el('strong',row.name),el('p',row.kind==='sshkey'?'SSH Key':'Secure Note','hint'),el('p',row.sources.join(' · '),'hint'));list.append(card)}
 if(!rows.length)list.append(el('p','저장된 공급 키가 없습니다. 아래에서 키를 추가하세요.','hint'));
 const pending=draft.credentials.filter(ref=>ref.source==='bitwarden'&&secretPurpose(ref)==='ssh-key'&&!rows.some(row=>row.item===ref.item&&row.kind===ref.kind));
 for(const ref of pending)list.append(el('p',ref.item+' · 저장 전 · 변경 검토에서 저장하면 일괄 공급에 포함됩니다.','hint'));
 for(const warning of secretFlow.status?.legacy?.warnings||[])list.append(el('p',warning,'notice'));
 const add=el('details',undefined,'group');add.append(el('summary','공급할 SSH 키 추가'));root.append(add);flowSearch(add,'ssh-key');
 if(secretFlow.key){const key=secretFlow.key,details=groupBox('선택한 키',add);details.append(el('strong',key.name),el('p',key.fingerprint,'hint'));
  details.append(button('공급 목록에 추가',()=>{flowReference(key,'ssh-key');mark();renderSecretFlow();toast('공급 목록 초안에 추가했습니다. 변경 검토에서 저장하세요.')},'btn'));
 }
 const cleanup=el('details',undefined,'control-more');cleanup.append(el('summary','작업 종료 · 이번에 공급한 키 해제'));root.append(cleanup);cleanup.append(flowButton('이번에 추가한 agent 키만 해제',{action:'cleanup'}),el('p','이 대시보드가 agent에 추가한 키만 해제합니다. Bitwarden 원본·공개키 파일·기존 agent 키·SSH 연결 설정은 유지합니다.','hint'));
 renderSecretInventory(root,'ssh-key');
 root.append(el('p','SSH 접속 대상·사용자·공개키 경로·연결별 키 선택은 Git 또는 원격 접속에서 관리합니다.','hint'),button('Git 설정 →',()=>navigate('connections'),'quiet'),button('원격 접속 설정 →',()=>navigate('servers'),'quiet'));
}
function renderSecretTokenWorkflow(){
 const root=$('page-body');root.replaceChildren();supplyHeader(root);
 const saved=groupBox('등록된 환경변수 공급',root),refs=draft.credentials.filter(ref=>ref.deliveryVariable);
 for(const ref of refs){const card=el('article',undefined,'auth-link-card');card.append(el('strong',ref.deliveryVariable),el('p','Bitwarden 항목: '+ref.item,'hint'));
  field(card,'공급할 환경변수 이름',ref.deliveryVariable,null,value=>{ref.deliveryVariable=value;mark()},'delivery-'+ref.id).placeholder='예: GITHUB_TOKEN 또는 API_KEY';
  if(['GH_TOKEN','GITHUB_TOKEN'].includes(ref.deliveryVariable))card.append(el('p','이 참조는 Bitwarden 연결 중 대시보드의 GitHub 관리 모듈 설치에도 사용합니다. Git 전역 인증은 바꾸지 않습니다.','hint'));
  card.append(el('pre',snapshot.secret_supply_command+' --reference '+ref.id+' -- PROGRAM ARGUMENTS','long-pre'));saved.append(card);
 }
 if(!refs.length)saved.append(el('p','등록된 환경변수 공급이 없습니다. 아래에서 항목과 변수 이름을 지정하세요.','hint'));
 saved.append(el('p','로그인에 사용한 터미널에서 PROGRAM ARGUMENTS를 실제 명령으로 바꿔 실행합니다. 값은 그 프로그램에만 전달하며 부모 셸이나 파일에 저장하지 않습니다. 저장 전 변경은 아직 실행에 반영되지 않습니다.','hint'));
 const add=groupBox('환경변수 공급 추가',root);flowSearch(add,'token');
 if(secretFlow.token){const token=secretFlow.token;add.append(el('p','선택한 항목: '+token.name+' · 값 본문은 표시하지 않습니다.','tool-state'));
  field(add,'프로그램이 읽을 환경변수 이름',secretFlow.deliveryVariable,null,value=>{secretFlow.deliveryVariable=value},'workflow-token-variable').placeholder='예: GITHUB_TOKEN 또는 API_KEY';
  add.append(button('환경변수 공급 목록에 추가',()=>{if(!validDeliveryVariable(secretFlow.deliveryVariable)){toast('유효한 환경변수 이름을 지정하세요. 시스템·인증 제어 변수는 사용할 수 없습니다.');return}const ref=flowReference(token,'token');ref.deliveryVariable=secretFlow.deliveryVariable;mark();renderSecretFlow();toast('초안에 추가했습니다. 변경 검토에서 저장하세요.')},'btn'));
 }
 root.append(button('변경 검토·저장 →',()=>navigate('plan'),'quiet'),el('p','기존 HTTPS Git·gh/glab 인증 설정은 유지됩니다. 연결별 인증은 Git 설정에서 관리합니다.','hint'),button('Git 인증 설정 →',()=>navigate('connections'),'quiet'));
}
function validDeliveryVariable(value){return /^[A-Z_][A-Z0-9_]*$/.test(value)&&!(/^(BW_|DOTFILES_|SSH_|GIT_|LD_|DYLD_|PYTHON|NODE_|BASH|ZSH)/).test(value)&&!['PATH','HOME','CODEX_HOME','SHELL','USER','PWD','OLDPWD','ENV','IFS','TMPDIR'].includes(value)}
function renderBitwardenSettings(){
 const root=$('page-body');root.replaceChildren();flowVault(root);
 const box=el('details',undefined,'control-more');box.append(el('summary','연결 유지 시간 · 고급 설정'));root.append(box);
 field(box,'다음 연결부터 유지할 시간',String(secretFlow.status?.connection_minutes||15),[['5','5분'],['15','15분'],['30','30분'],['60','60분']],value=>flowAction({action:'set_connection_lifetime',minutes:Number(value)}),'vault-connection-lifetime');
 box.append(el('p','대시보드가 세션을 메모리에 유지할 시간입니다. 변경은 다음 연결부터 적용하며 Bitwarden 자체 잠금 정책·SSH agent 키 수명은 바꾸지 않습니다.','hint'));
}
