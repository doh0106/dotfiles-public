'use strict';
// Browser state contains metadata and public keys only. Vault sessions live in the local broker.
const secretFlow={status:null,statusAttempted:false,busy:false,error:'',handoff:null,key:null,token:null,target:'',tokenTarget:'',tokenRole:'api',tokenDelivery:'connection',deliveryVariable:'SERVICE_TOKEN',programReference:'',username:'',searches:{'ssh-key':{query:'',items:[]},token:{query:'',items:[]}}};
async function workflowRequest(request){const response=await fetch('/api/secrets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const data=await response.json();if(!response.ok)throw Error(data.error);return data;}
function renderSecretFlow(){if(view==='secrets')renderSecretSshWorkflow();else if(view==='secret-tokens')renderSecretTokenWorkflow();else if(view==='providers')renderProviders();else if(view==='secret-links')renderSecretLinks();attachDomainNavigation();}
async function flowAction(request,done=()=>{}){
 if(secretFlow.busy)return;secretFlow.busy=true;secretFlow.error='';renderSecretFlow();
 try{const previous=secretFlow.status?.generation,result=await workflowRequest(request);done(result);secretFlow.status=request.action==='status'?result:await workflowRequest({action:'status'});if(previous&&previous!==secretFlow.status.generation){secretFlow.key=null;secretFlow.token=null;for(const search of Object.values(secretFlow.searches))search.items=[]}if(!secretFlow.key&&secretFlow.status.prepared?.length)secretFlow.key=secretFlow.status.prepared.at(-1);}
 catch(error){secretFlow.error=error.message}
 finally{secretFlow.busy=false;renderSecretFlow()}
}
function flowButton(title,request,done,disabled=false){const b=button(title,()=>flowAction(typeof request==='function'?request():request,done),'btn');b.disabled=secretFlow.busy||disabled||snapshot.design_preview;return b;}
function flowStep(root,number,title,text){const box=groupBox((number?number+'. ':'')+title,root);if(text)box.append(el('p',text,'tool-state'));return box;}
function flowVault(root){
 const box=flowStep(root,'','Bitwarden 연결','로그인 정보는 터미널에서 입력합니다. 대시보드 연결은 15분 동안 유지하며 세션 값을 브라우저나 파일에 저장하지 않습니다.');
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
 const search=secretFlow.searches[purpose],box=flowStep(root,'','저장소 항목 검색·선택','이름으로 검색합니다. 목록에는 이름·항목 종류만 표시하며 개인키·토큰 본문은 표시하지 않습니다.');
 const input=field(box,'검색할 항목 이름',search.query,null,value=>{search.query=value},'vault-item-search');input.placeholder=purpose==='ssh-key'?'예: github ssh key':'예: github token';
 const lookup=()=>({action:'search',query:search.query,purpose});
 box.append(flowButton('항목 검색',lookup,result=>{search.items=result.items},!secretFlow.status?.connected));
 if(search.items.length){const list=el('div',undefined,'vault-results');for(const item of search.items){const row=el('article',undefined,'vault-item');row.append(el('strong',item.name),el('p',({note:'Secure Note',sshkey:'SSH Key',login:'Login'})[item.kind]+' · 항목 ID '+item.id,'hint'));
  row.append(flowButton(purpose==='ssh-key'?'선택하고 공개키 준비':'선택하고 토큰 형식 확인',{action:purpose==='ssh-key'?'prepare_public':'check_token',item:item.id},result=>{if(purpose==='ssh-key')secretFlow.key=result;else secretFlow.token=result},!secretFlow.status?.connected));list.append(row)}box.append(list);}
 else box.append(el('p','2자 이상 검색어를 입력하세요. SSH 키는 SSH Key·Secure Note, 토큰은 Secure Note·Login 항목을 선택할 수 있습니다.','hint'));
}
function flowReference(item,purpose,username=null){
 let ref=draft.credentials.find(ref=>ref.source==='bitwarden'&&ref.item===item.item&&ref.kind===item.kind&&secretPurpose(ref)===purpose&&(username===null||ref.username===username));
 if(!ref){ref=makeCredential(uniqueId((purpose==='ssh-key'?'ssh-key-':'token-')+(item.item.toLowerCase().replace(/[^a-z0-9-]/g,'-').slice(0,40)||'item'),draft.credentials));Object.assign(ref,{purpose,kind:item.kind,item:item.item,username:username||''});draft.credentials.push(ref)}ref.purpose=purpose;return ref;
}
function flowConnectionRecords(kind){return draft.connections.filter(c=>kind==='ssh'?c.method==='ssh':c.kind==='git'&&(c.method==='https'||c.api.enabled)).map(c=>({id:c.id,title:c.name,lines:connectionLines(c)}));}
function flowRegisterKey(){
 const key=secretFlow.key,c=draft.connections.find(c=>c.id===secretFlow.target);if(!key?.saved||!c||c.method!=='ssh'){toast('공개키를 저장하고 SSH 연결을 선택하세요.');return}
 const ref=flowReference(key,'ssh-key'),alias=snapshot.host_state?.candidates.find(item=>['ssh','git-ssh'].includes(item.category)&&item.label===c.host);
 if(sshMode(c)==='system'&&alias){c.host=alias.details.hostname||c.host;c.sshUser=alias.details.user||c.sshUser;}
 c.sshMode='key';c.publicKey=key.path;c.credential=ref.id;
 if(!c.sshUser&&c.kind==='git'&&knownGitSshHost(c))c.sshUser='git';
 if(key.dedicated_agent)c.agentSocket=key.agent_socket;else delete c.agentSocket;
 mark();toast('키·공급 정책과 연결을 초안에 반영했습니다. 변경 검토에서 저장·적용하세요.');renderSecretFlow();
}
function renderSecretSshWorkflow(){
 const root=$('page-body');root.replaceChildren();renderKeyReadiness(root);renderLegacyRegistrations(root);const recurring=groupBox('작업할 때 · 인증 준비',root);recurring.append(el('p','저장한 설정은 유지됩니다. 보관소 연결이나 agent의 키가 만료되었을 때만 다시 준비하세요.','tool-state'));flowVault(recurring);
 const setup=el('details',undefined,'group');setup.open=!draft.connections.some(c=>c.method==='ssh'&&sshMode(c)==='key');setup.append(el('summary','처음 한 번 · 키와 접속 설정 등록'),el('p','항목 선택·공개키 파일·사용 연결·정책을 저장합니다. 완료한 설정은 매번 만들지 않아도 됩니다.','hint'));root.append(setup);flowSearch(setup,'ssh-key');
 const box=flowStep(setup,'','공개키 파일 준비','공개키는 .pub 파일로 저장합니다. 공개키 파일 저장과 agent 공급 버튼은 즉시 실행됩니다. 설정 초안 저장과 별개이며 개인키는 파일로 복사하지 않습니다.');const key=secretFlow.key;
 if(!key){box.append(el('p','앞 단계에서 항목을 선택하면 공개키와 지문을 확인할 수 있습니다.','hint'));}
 else{
  box.append(el('strong',key.name),el('p',key.fingerprint,'tool-state'),el('pre',key.public,'long-pre'));
  if(key.existing_connections?.length)box.append(el('p','기존 공개키와 일치 · '+key.existing_connections.join(', ')+' · 파일을 다시 만들지 않고 사용합니다.','hint'));
  const keyPath=field(box,'공개키 저장 위치',key.path,null,value=>{key.path=value;key.saved=false},'workflow-public-key');keyPath.placeholder='예: ~/.ssh/keys/personal.pub';
  box.append(flowButton(key.saved?'공개키 저장 확인됨 · 다시 확인':'공개키 파일 저장',()=>({action:'save_public',id:key.id,path:key.path}),result=>{secretFlow.key=result}));
  const supplyBox=groupBox('선택한 키를 이번 작업에 준비',recurring);
  field(supplyBox,'새로 공급하는 키의 유지 시간 · 초',draft.session.keyLifetime,null,value=>{draft.session.keyLifetime=Number(value);mark()},'workflow-key-ttl','number');
  supplyBox.append(el('p','60~86400초. 이미 agent에 있는 동일한 키는 재사용하며 기존 유지 시간을 바꾸지 않습니다. 이 도구가 공급한 키만 정리합니다. 새 정책은 초안 저장으로 유지됩니다.','hint'));
  const supply=flowButton('SSH agent에 키 공급',()=>({action:'supply_key',id:key.id,lifetime:draft.session.keyLifetime}),result=>{secretFlow.key=result},!key.saved||!secretFlow.status?.connected);supplyBox.append(supply);keyPath.addEventListener('input',()=>{supply.disabled=true});
  if(key.loaded)supplyBox.append(badge('공급 실행 완료 · 서버 접속은 별도 확인','green'),el('p',key.dedicated_agent?'전용 agent를 사용합니다. 연결 설정에 이 소켓을 함께 지정하며 대시보드 종료 후 다시 공급해야 합니다.':'현재 agent를 재사용합니다. 다른 키의 설정은 변경하지 않습니다.','hint'));
 }
 const target=flowStep(setup,'','접속 설정 연결·저장','이 단계는 설정 초안을 만듭니다. 검토·저장·적용과 실제 서버 접속 확인은 별도로 진행합니다.');
 recordChoiceField(target,'키를 사용할 SSH 연결',secretFlow.target,()=>flowConnectionRecords('ssh'),value=>{secretFlow.target=value;renderSecretFlow()},'workflow-key-target','SSH 연결 선택');
 const apply=button('선택한 키·정책을 연결 초안에 반영',flowRegisterKey,'btn primary');apply.disabled=!key?.saved||!secretFlow.target||secretFlow.busy;target.append(apply,button('Git 연결 추가·확인 →',()=>navigate('connections',{primary:true}),'quiet'),button('원격 SSH 대상 추가·확인 →',()=>navigate('servers',{primary:true}),'quiet'),button('변경 검토·적용 →',()=>navigate('plan',{primary:true}),'quiet'));
 target.append(el('p','새 연결에는 서버 주소·SSH 사용자가 필요합니다. 공개키의 서버 등록과 실제 접속 성공은 이 과정에서 자동 처리하지 않습니다.','hint'));
 const cleanup=flowStep(root,'','작업 끝 · 이번에 추가한 agent 키 해제','메모리의 agent에서 이번 대시보드가 추가한 키만 해제합니다. Bitwarden 원본, 로컬 .pub 파일, GitHub 등록 키, 저장한 접속 설정은 삭제하지 않습니다. 원래 agent에 있던 키도 유지합니다.');cleanup.append(flowButton('이번에 추가한 agent 키만 해제',{action:'cleanup'},()=>{if(secretFlow.key)secretFlow.key.loaded=false}));
 renderSecretInventory(root,'ssh-key');
}
function renderSecretTokenWorkflow(){
 const root=$('page-body');root.replaceChildren();flowVault(root);flowSearch(root,'token');
 const box=flowStep(root,'','토큰 공급 대상 지정','토큰 본문은 표시·저장하지 않습니다. 선택한 HTTPS Git 또는 API 도구가 요청할 때만 해당 호스트의 명령에 공급합니다.');const token=secretFlow.token;
 if(token)box.append(badge('한 줄 토큰 형식 확인됨','green'),el('p',token.name+' · 실제 권한·만료·서버 접근은 아직 확인하지 않았습니다.','hint'));
 field(box,'토큰 공급 경로',secretFlow.tokenDelivery,[['connection','HTTPS Git·GitHub/GitLab API'],['program','다른 프로그램의 환경변수']],value=>{secretFlow.tokenDelivery=value;renderSecretFlow()},'workflow-token-delivery');
 if(secretFlow.tokenDelivery==='program'){renderProgramSupply(box,token);renderSecretInventory(root,'token');return;}
 recordChoiceField(box,'토큰을 사용할 연결',secretFlow.tokenTarget,()=>flowConnectionRecords('token'),value=>{secretFlow.tokenTarget=value;renderSecretFlow()},'workflow-token-target','HTTPS Git 또는 API 연결 선택');
 const c=draft.connections.find(c=>c.id===secretFlow.tokenTarget),roles=[];if(c?.method==='https')roles.push(['git','HTTPS Git 인증']);if(c?.api.enabled)roles.push(['api','PR·이슈 API 도구']);
 if(roles.length&&!roles.some(([id])=>id===secretFlow.tokenRole))secretFlow.tokenRole=roles[0][0];
 if(roles.length)field(box,'사용할 기능',secretFlow.tokenRole,roles,value=>{secretFlow.tokenRole=value;renderSecretFlow()},'workflow-token-role');
 if(secretFlow.tokenRole==='git'&&c?.method==='https'){field(box,'HTTPS Git 인증 사용자명',secretFlow.username,null,value=>{secretFlow.username=value},'workflow-token-user').placeholder='예: x-access-token 또는 서비스 사용자명';}
 const apply=button('토큰 공급 설정을 초안에 반영',()=>{
  if(!token||!c||!roles.some(([id])=>id===secretFlow.tokenRole)){toast('토큰과 사용할 기능을 선택하세요.');return}
  if(secretFlow.tokenRole==='git'&&!secretFlow.username.trim()){toast('HTTPS Git 인증 사용자명을 입력하세요.');return}
  const ref=flowReference(token,'token',secretFlow.tokenRole==='git'?secretFlow.username.trim():null);if(secretFlow.tokenRole==='git')c.credential=ref.id;else c.api.credential=ref.id;mark();toast('토큰 보관 위치와 공급 대상을 초안에 반영했습니다.');renderSecretFlow();
 },'btn primary');apply.disabled=!token||!c||secretFlow.busy;box.append(apply,button('Git·API 연결 설정 →',()=>navigate('connections',{primary:true}),'quiet'),button('변경 검토·적용 →',()=>navigate('plan',{primary:true}),'quiet'));
 box.append(el('p','저장·적용 후 로그인 연결에 사용한 터미널에서 작업하세요. HTTPS Git은 credential helper, API는 bwgh/bwglab 연결별 명령이 토큰을 공급합니다. 서비스 로그인·서버 권한 확인은 별도입니다.','hint'));renderSecretInventory(root,'token');
}

function renderProgramSupply(box,token){
 field(box,'프로그램이 읽을 토큰 환경변수 이름',secretFlow.deliveryVariable,null,value=>{secretFlow.deliveryVariable=value},'workflow-token-variable').placeholder='예: JIRA_TOKEN';
 const apply=button('프로그램용 토큰 참조를 초안에 반영',()=>{
  if(!token||!(/^[A-Z][A-Z0-9_]*_TOKEN$/).test(secretFlow.deliveryVariable)){toast('SERVICE_TOKEN 형식의 변수 이름을 입력하세요.');return;}
  const ref=flowReference(token,'token');ref.deliveryVariable=secretFlow.deliveryVariable;secretFlow.programReference=ref.id;mark();renderSecretFlow();toast('토큰 공급 참조를 초안에 반영했습니다. 검토·저장 후 명령을 실행하세요.');
 },'btn primary');apply.disabled=!token||secretFlow.busy;box.append(apply,button('변경 검토·적용 →',()=>navigate('plan',{primary:true}),'quiet'));
 box.append(el('p','저장 후 로그인에 사용한 터미널에서 아래 형식으로 대상 프로그램을 실행하세요. 프로그램이 지정한 환경변수를 읽어야 합니다. 기존 Jira·Confluence 인증 파일은 변경하지 않습니다.','hint'));
 if(secretFlow.programReference)box.append(el('pre',snapshot.secret_supply_command+' --reference '+secretFlow.programReference+' -- PROGRAM ARGUMENTS','long-pre'));
}

function renderKeyReadiness(root){
 const rows=secretFlow.status?.keys||[],box=groupBox('현재 SSH 인증 준비 상태',root);
 const selected=rows.find(row=>row.id==='prepared:'+secretFlow.key?.id)||rows.find(row=>row.id===secretFlow.target),ready=rows.filter(row=>row.state==='ready');
 const next=selected?.state==='ready'?'선택한 키는 준비됐습니다. 접속 설정의 저장·적용 여부를 확인하세요.':selected?'아래에서 선택한 키를 다시 준비하세요.':ready.length?'준비된 키가 있습니다. 사용할 연결의 상태를 확인하세요.':rows.length?'저장한 키의 상태를 확인하고 필요한 키만 다시 준비하세요.':'처음 한 번 항목을 선택하고 키·접속 설정을 등록하세요.';
 box.append(el('strong','다음 할 일: '+next),el('p','이 대시보드 또는 연결에 지정한 agent 기준입니다. 다른 터미널의 agent는 다를 수 있으며 실제 서버 접속·권한 확인은 별도입니다.','hint'),flowButton('키 준비 상태 새로 확인',{action:'status'}));
 for(const row of rows){const card=el('article',undefined,'auth-link-card');card.append(el('strong',row.name),badge(({ready:'키 준비됨',not_loaded:'키 공급 필요',agent_unavailable:'agent 연결 필요',public_missing:'공개키 파일 확인 필요'})[row.state],row.state==='ready'?'green':'amber'),el('p',row.path,'hint'),el('p',row.source==='existing'?'기존 SSH 설정에서 감지 · 원본 유지':row.source==='saved'?'저장한 접속 설정':'이번에 준비한 공개키','hint'));
  if(row.state==='ready')card.append(el('p',row.expires_in===null?'남은 유지 시간은 알 수 없습니다. 기존 키의 TTL은 변경하지 않습니다.':'이 대시보드가 추가한 키 · 약 '+Math.ceil(row.expires_in/60)+'분 남음','hint'));
  else if(row.source==='saved')card.append(flowButton('저장한 이 키 다시 준비',{action:'prepare_saved',connection:row.id},result=>{secretFlow.key=result},!secretFlow.status?.connected));
  else if(row.source==='existing')card.append(el('p','기존 bws 등 공급 도구로 준비하거나 처음 설정에서 이 키를 등록하세요.','hint'));
  box.append(card);
 }
 if(!secretFlow.status)box.append(el('p','상태를 확인하는 중입니다.','hint'));
}

function renderLegacyRegistrations(root){
 const legacy=secretFlow.status?.legacy;if(!legacy)return;
 const box=groupBox('기존 bws 등록 키',root);
 box.append(el('p','기존 등록 목록을 그대로 읽습니다. 항목을 다시 검색하거나 입력할 필요가 없습니다. 가져오기는 관리용 참조만 초안에 추가하며 기존 bws·인증은 유지합니다.','hint'));
 for(const row of legacy.items){
  const card=el('article',undefined,'auth-link-card'),ref=draft.credentials.find(ref=>ref.source==='bitwarden'&&ref.item===row.item&&ref.kind===row.kind&&secretPurpose(ref)==='ssh-key');
  card.append(el('strong',row.name),badge(ref?'관리 설정에 있음':'기존 bws에 등록됨',ref?'green':'amber'),el('p',row.kind==='sshkey'?'SSH Key':'Secure Note','hint'),el('p',row.sources.join(' · '),'hint'));
  const add=button(ref?'관리 설정에 가져옴':'관리 설정에 가져오기',()=>{flowReference(row,'ssh-key');mark();renderSecretFlow();toast('기존 키 참조를 초안에 가져왔습니다. 변경 검토에서 저장하세요.')},'btn');add.disabled=Boolean(ref)||secretFlow.busy||snapshot.design_preview;
  card.append(add,flowButton('이 키 사용 · 기존 공개키 확인',{action:'prepare_registered',registration:row.id},result=>{secretFlow.key=result},!secretFlow.status?.connected));
  card.append(el('p','키 준비는 Bitwarden 연결 후 가능합니다. 일치하는 기존 공개키는 자동으로 재사용하며 agent 공급은 별도로 선택합니다.','hint'));box.append(card);
 }
 if(!legacy.items.length)box.append(el('p','감지된 bws SSH 키 등록이 없습니다. 다른 목록을 사용한다면 대시보드를 시작할 때 DOTFILES_SECRETS_MANIFEST로 지정하세요.','hint'));
 for(const warning of legacy.warnings)box.append(el('p',warning,'notice'));
}
