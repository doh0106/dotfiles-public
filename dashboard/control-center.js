'use strict';
const controlState={generation:0,loaded:false,busy:false,error:'',job:null,update:null,timer:null};
async function controlRequest(body){const response=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await response.json();if(!response.ok)throw Error(result.error);return result;}
async function loadControl(){
 const generation=controlState.generation;
 try{const result=await controlRequest({action:'status'});if(generation!==controlState.generation)return;Object.assign(controlState,result,{loaded:true,error:''});secretFlow.status=await workflowRequest({action:'status'});if(generation!==controlState.generation)return;if(result.job?.status==='done'&&controlState.refreshedAt!==result.job.started_at){const current=await api('/api/state');snapshot.shared_environment=current.shared_environment;snapshot.definitions=current.definitions;snapshot.auth_status=current.auth_status;if(JSON.stringify(current.state)===JSON.stringify(baseline))snapshot.revision=current.revision;controlState.refreshedAt=result.job.started_at}if(view==='overview')renderControlCenter();if(result.busy){clearTimeout(controlState.timer);controlState.timer=setTimeout(loadControl,1200)}}catch(error){if(generation!==controlState.generation)return;controlState.error=error.message;if(view==='overview')renderControlCenter()}
}
async function runControl(action){
 if(controlState.busy)return;controlState.generation++;clearTimeout(controlState.timer);controlState.busy=true;controlState.error='';renderControlCenter();
 try{
  if(action==='apply'&&(snapshot.revision==='new'||diff(baseline,draft).length)){snapshot=await api('/api/settings',draft);draft=clone(snapshot.state);baseline=clone(snapshot.state);mark()}
  const result=await controlRequest({action,revision:snapshot.revision});Object.assign(controlState,result);await loadControl();
 }catch(error){controlState.busy=false;controlState.error=error.message;renderControlCenter()}
}
async function supplyFromHome(){
 if(controlState.busy)return;controlState.generation++;clearTimeout(controlState.timer);controlState.busy=true;renderControlCenter();
 try{await workflowRequest({action:'supply_all',lifetime:draft.session.keyLifetime});secretFlow.status=await workflowRequest({action:'status'});controlState.error=''}catch(error){controlState.error=error.message}finally{controlState.busy=false;renderControlCenter()}
}
function controlButton(title,action,primary=false){const result=button(title,()=>runControl(action),primary?'btn primary':'btn');result.disabled=controlState.busy||snapshot.design_preview;return result}
function portableSettings(state,keys){
 const result=JSON.parse(JSON.stringify(state));
 for(const key of keys){
  if(result.credentials.some(ref=>ref.source==='bitwarden'&&ref.item===key.item&&ref.kind===key.kind&&(ref.purpose==='ssh-key'||!ref.purpose&&(result.connections||[]).some(c=>c.method==='ssh'&&c.credential===ref.id))))continue;
  const id=uniqueId('ssh-key-'+key.item.toLowerCase().replace(/[^a-z0-9-]/g,'-').slice(0,40),result.credentials);
  result.credentials.push({id,purpose:'ssh-key',source:'bitwarden',kind:key.kind,item:key.item,variable:'',helper:'cache',username:''});
 }
 return result;
}
function renderControlCenter(){
 const root=$('page-body');root.replaceChildren();
 const layout=el('div',undefined,'control-layout'),main=el('section',undefined,'control-main'),attention=el('aside',undefined,'control-attention');layout.append(main,attention);root.append(layout);
 const hero=el('section',undefined,'control-hero');hero.append(el('h2','내 환경 적용'),el('p','새 컴퓨터에서도 여기서 이어갑니다. 필요한 도구를 선택하고 적용한 뒤, 필요한 인증만 연결하세요.'));
 const selected=snapshot.definitions.filter(f=>draft.features[f.id]?.enabled).map(f=>f.name),changes=diff(baseline,draft).length;
 hero.append(el('p','Git·셸·Bitwarden CLI 등 기본 도구와 선택한 프로그램 중 없는 것만 설치합니다. 관리자 승인이 필요한 항목은 조치할 일을 표시합니다.','hint'));
 hero.append(el('p',selected.length?'설치·설정할 도구: '+selected.join(', '):'추가 도구 선택 없음 · 기존 설정은 유지합니다.','hint'),controlButton(changes||snapshot.revision==='new'?'선택한 설정 저장·적용':'내 환경 적용','apply',true),button('도구·설정 선택',()=>navigate('tools'),'quiet'));
 const more=el('details',undefined,'control-more');more.append(el('summary','설정 가져오기·내보내기 · 더 보기'),button('기존 Git·SSH·셸 설정 확인',()=>navigate('existing'),'quiet'),button('세부 설정 검토',()=>navigate('plan'),'quiet'));
 const file=el('input');file.type='file';file.accept='.json,application/json';file.setAttribute('aria-label','다른 컴퓨터의 환경 설정 불러오기');file.onchange=async()=>{try{const input=file.files[0];if(!input||input.size>262144)throw Error('설정 JSON 크기를 확인하세요.');const state=JSON.parse(await input.text());await api('/api/preview',state);draft=state;mark();renderControlCenter();toast('설정을 초안에 불러왔습니다. 경로와 도구를 검토하고 적용하세요.')}catch(error){toast(error.message)}};
 more.append(el('p','다른 컴퓨터에서 내보낸 설정 JSON을 불러오세요. 비밀 값은 포함하지 않습니다. 기기별 폴더 경로는 검토해야 합니다.','hint'),file,button('현재 설정 내보내기',()=>{const exported=portableSettings(draft,secretFlow.status?.registered_keys||[]);const url=URL.createObjectURL(new Blob([JSON.stringify(exported,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='dotfiles-settings.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)},'quiet'));
 hero.append(more);main.append(hero);
 const bar=el('div',undefined,'control-statusbar'),refresh=button('↻',loadControl,'quiet');refresh.setAttribute('aria-label','환경·인증 상태 새로고침');bar.append(el('span',secretFlow.status?.connected?'Bitwarden 연결됨':'Bitwarden 연결 필요','hint'),el('span','SSH agent: '+snapshot.auth_status.agent,'hint'),refresh);main.prepend(bar);
 if(controlState.error){const error=el('p',controlState.error,'notice');error.setAttribute('role','alert');attention.prepend(error)}
 if(controlState.job){const job=controlState.job,stale=job.action==='apply'&&(job.revision!==snapshot.revision||diff(baseline,draft).length>0),progress=groupBox('진행 상황',main);progress.append(badge(stale?'이전 설정의 실행 기록':({running:'진행 중',done:'완료',needs_action:'조치 필요',interrupted:'중단됨'})[job.status]||job.status,job.status==='done'?'green':'amber'));
  const steps=el('ol',undefined,'control-steps');for(const step of job.steps){const row=el('li');row.append(el('strong',step.title),el('span',({pending:'대기',running:'진행 중',done:'완료',needs_action:'조치 필요'})[step.state]||step.state,'hint'));steps.append(row)}progress.append(steps,el('p',job.message,'hint'));
  if(job.status==='needs_action'||job.status==='interrupted')progress.append(controlButton('다시 확인하고 이어가기',job.action),button('설치 안내 보기',()=>navigate('plan'),'quiet'),button('Git·인증 설정',()=>navigate('connections'),'quiet'));
  if(job.restart_required&&!controlState.busy)progress.append(button('업데이트 적용 · 대시보드 재시작',async()=>{try{await controlRequest({action:'restart'});toast('대시보드를 다시 엽니다. Bitwarden 연결은 다시 필요합니다.');setTimeout(()=>location.reload(),1800)}catch(error){toast(error.message)}},'btn primary'));
 }
 const tasks=el('section',undefined,'control-tasks');attention.append(el('h2','인증·SSH 키'),tasks);
 function task(title,text,action){const row=el('div',undefined,'control-task');const content=el('div');content.append(el('h3',title),el('p',text,'hint'));row.append(content,action);tasks.append(row)}
 task('Bitwarden 연결','키·값을 새로 가져올 때 연결합니다. 이미 agent에 공급한 키는 별도로 유지됩니다.',button(secretFlow.status?.connected?'연결 설정':'연결하기',()=>navigate('providers'),'btn'));
 const keyButton=button('등록된 SSH 키 모두 공급',supplyFromHome,'btn');keyButton.disabled=!secretFlow.status?.connected||controlState.busy||snapshot.design_preview;
 task('SSH 키 공급',(secretFlow.status?.registered_keys?.length||0)+'개 등록 · bws처럼 agent에 공급합니다. agent 설정은 원격 접속에서 관리합니다.',keyButton);
 if(secretFlow.status?.last_supply){const report=el('ul');for(const row of secretFlow.status.last_supply.results)report.append(el('li',row.item+' · '+({added:'공급 완료',reused:'기존 키 재사용',failed:'공급 실패'})[row.state]));tasks.append(report);if(secretFlow.status.last_supply.dedicated_agent)tasks.append(el('p','별도 agent가 준비됐습니다. 원격 접속 → SSH agent에서 터미널 연결 방법을 확인하세요.','hint'))}
 const optional=el('details',undefined,'control-more control-optional');optional.append(el('summary','필요할 때 추가 · 서비스·프로젝트·원격 접속'));root.append(optional);const optionalTasks=el('section',undefined,'control-tasks');optional.append(optionalTasks);
 function extra(title,text,action){const row=el('div',undefined,'control-task'),content=el('div');content.append(el('h3',title),el('p',text,'hint'));row.append(content,action);optionalTasks.append(row)}
 extra('외부 서비스',snapshot.shared_environment?.availability==='available'?'Jira·Confluence·Google 인증 설정을 이어갑니다.':'외부 서비스 관리 모듈을 설치·연결합니다. 비공개 저장소 접근 권한이 필요합니다.',snapshot.shared_environment?.availability==='available'?button('서비스 인증 열기',()=>navigate('services'),'btn'):controlButton('서비스 관리 설치','services'));
 extra('프로젝트 실행 환경','컨테이너 개발이 필요하면 실행 도구를 연결합니다. Docker 로그인·OS 권한은 해당 안내에서 진행합니다.',controlButton('실행 도구 설치·연결','runtime'));
 extra('원격 접속','SSH agent·접속 대상·Tailscale과 집 WSL 접속을 관리합니다.',button('원격 접속 열기',()=>navigate('servers'),'btn'));
 const updates=el('details',undefined,'control-more');updates.append(el('summary','환경 코드 업데이트'),el('p','이 대시보드의 현재 추적 브랜치에서 최신 변경을 확인합니다. 로컬 수정이 있으면 보존하고 중단하며, 자동 병합은 하지 않습니다.','hint'),controlButton('최신 변경 확인','check_update'),controlButton('업데이트 가져오기','update'));
 if(controlState.update)updates.append(el('p',controlState.update.branch+' · 가져올 변경 '+controlState.update.behind+'개 · 로컬 커밋 '+controlState.update.ahead+'개','hint'));root.append(updates);
 if(!controlState.loaded&&!controlState.busy&&!snapshot.design_preview){controlState.loaded=true;queueMicrotask(loadControl)}
}

function renderStartGuide(){
 const root=$('page-body');root.replaceChildren();root.append(el('h2','이 컴퓨터에서 시작하기'),el('p','처음 한 번 Git·Python으로 대시보드를 실행한 뒤, 아래 순서로 진행합니다.','hint'));
 const steps=[['환경 선택','다른 컴퓨터의 설정 JSON을 불러오거나 필요한 도구를 고릅니다.','overview','내 환경 열기'],['설치·설정 적용','내 환경에서 선택한 설정 저장·적용을 누릅니다. 설치와 적용의 진행 결과를 확인하세요.','overview','설치·적용하기'],['Bitwarden 연결','이 화면에서 잠금을 해제합니다. 보관 항목의 생성·편집은 Bitwarden에서 합니다.','providers','Bitwarden 연결'],['SSH 키 공급','등록된 키를 agent에 한 번에 공급합니다. 새 키를 다시 등록할 필요가 없습니다.','key-supply','SSH agent 열기'],['필요한 서비스 추가','Jira·Google·프로젝트 실행 환경·원격 접속은 내 환경의 선택 기능에서 이어갑니다.','overview','이어서 설정']];
 const list=el('ol',undefined,'control-steps');for(const [title,text,target,action] of steps){const row=el('li');row.append(el('h3',title),el('p',text,'hint'),button(action,()=>navigate(target,{primary:true}),'btn'));list.append(row)}root.append(list);
}
