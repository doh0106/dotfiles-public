'use strict';
// Agent UI knows local key paths, sockets and lifetime; no vault session or provider.
const agentState={status:null,busy:false,error:'',path:'',socketDraft:undefined,result:null,loaded:false};
async function agentRequest(request){const response=await fetch('/api/ssh-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const result=await response.json();if(!response.ok)throw Error(result.error);return result;}
async function agentAction(request){
 if(agentState.busy||snapshot.design_preview)return;agentState.busy=true;agentState.error='';renderAgentManager();
 try{const result=await agentRequest(request);if(request.action==='register_file')agentState.result=result;agentState.status=request.action==='status'?result:await agentRequest({action:'status'});agentState.loaded=true;snapshot.auth_status.agent=agentState.status.agent_ready?(agentState.status.key_count?'키 있음':'연결됨 · 키 없음'):'연결 안 됨'}
 catch(error){agentState.error=error.message}finally{agentState.busy=false;if(view==='key-supply')renderAgentManager()}
}
function agentButton(title,request,primary=false){const action=button(title,()=>agentAction(typeof request==='function'?request():request),primary?'btn primary':'btn');action.disabled=agentState.busy||snapshot.design_preview;return action}
function renderAgentManager(){
 const root=$('page-body');root.replaceChildren();const status=agentState.status;
 const bar=el('div',undefined,'control-statusbar');bar.append(badge(status?.agent_ready?'agent 연결됨 · 키 '+status.key_count+'개':'agent 미연결',status?.agent_ready?'green':'amber'));const refresh=agentButton('↻',{action:'status'});refresh.setAttribute('aria-label','SSH agent 상태 새로고침');bar.append(refresh);root.append(bar);
 if(agentState.error){const error=el('p',agentState.error,'notice');error.setAttribute('role','alert');root.append(error)}
 const layout=el('div',undefined,'control-layout'),main=el('section'),aside=el('aside');layout.append(main,aside);root.append(layout);
 const add=groupBox('준비된 개인키 등록',main);add.append(el('p','이 컴퓨터에 준비된 개인키 파일을 agent에 등록합니다. 파일을 복사하거나 SSH 접속 설정을 바꾸지 않습니다.','hint'));
 field(add,'개인키 파일 경로',agentState.path,null,value=>{agentState.path=value;register.disabled=agentState.busy||snapshot.design_preview||!value.trim()},'agent-private-path').placeholder='예: ~/.ssh/id_ed25519';
 field(add,'새로 등록할 키 유지 시간 · 초',draft.session.keyLifetime,null,value=>{draft.session.keyLifetime=Number(value);mark()},'key-lifetime','number');
 const register=agentButton('개인키 파일을 agent에 등록',()=>({action:'register_file',path:agentState.path,lifetime:draft.session.keyLifetime}),true);register.disabled=register.disabled||!agentState.path.trim();add.append(register,el('p','홈 안의 본인 소유 파일과 600/400 권한을 확인합니다. .pub만으로는 등록할 수 없습니다. 암호가 걸린 파일은 기존 대화형 SSH 도구에서 먼저 준비하세요. 이미 등록된 키의 유지 시간은 바꾸지 않습니다.','hint'));
 const report=agentState.result||status?.last_registration;
 if(report){const results=groupBox('최근 등록 결과',main);for(const row of report.results)results.append(el('p',row.name+' · '+({added:'등록 완료',reused:'기존 키 재사용',failed:'개인키·파일 형식 확인 필요'})[row.state],row.state==='failed'?'notice':'hint'))}
 const current=groupBox('사용할 agent',aside);current.append(el('p',status?.agent_socket||'등록할 때 기존 agent를 찾거나 대시보드 agent를 준비합니다.','source-path'),el('p','대시보드가 등록한 키 '+(status?.managed_keys||0)+'개 · 다른 도구가 등록한 기존 키도 함께 사용할 수 있습니다.','hint'));
 if(status?.keys?.length){const keys=el('ul');for(const key of status.keys){const row=el('li');row.append(el('p',key.fingerprint,'source-path'),el('small',key.managed?'대시보드 등록 · 약 '+Math.ceil(key.expires_in/60)+'분 남음':'기존 키 · 유지 시간은 원래 정책을 따릅니다.','hint'));keys.append(row)}current.append(keys)}
 const options=el('details',undefined,'control-more');options.append(el('summary','agent 선택·소켓 설정'));current.append(options);
 if(status){field(options,'agent 소켓 · 비우면 자동',agentState.socketDraft??status.preference,null,value=>{agentState.socketDraft=value},'agent-socket').placeholder='예: /private/tmp/.../agent.sock';options.append(agentButton('선택 저장',()=>({action:'set_agent',socket:agentState.socketDraft??status.preference})),agentButton('기존 agent 사용',{action:'set_agent',socket:status.inherited_socket||''}),agentButton('대시보드 agent 사용',{action:'set_agent',socket:status.dedicated_socket}));}
 const cleanup=el('details',undefined,'control-more');cleanup.append(el('summary','등록한 키 해제'),el('p','대시보드가 추가한 키만 agent에서 해제합니다. 개인키 파일·기존 agent 키·접속 설정은 유지합니다.','hint'),agentButton('대시보드가 등록한 키 해제',{action:'cleanup'}));root.append(cleanup);
 root.append(el('p','다른 저장소에서 키를 가져오려면 비밀 관리에서 준비·공급하세요. 이 화면은 저장소 연결 없이 사용할 수 있습니다.','hint'),button('비밀 관리에서 키 준비·공급 →',()=>navigate('secret-keys'),'quiet'));
 if(!agentState.loaded&&!agentState.busy&&!snapshot.design_preview){agentState.loaded=true;queueMicrotask(()=>agentAction({action:'status'}))}
}
