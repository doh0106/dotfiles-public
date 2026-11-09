'use strict';
// Setup acknowledgements are per-machine metadata, never proof of a live login.
labels.overview='환경 현황';
let progressBasis=null,progressSnapshot=null,recordingSetup=false;
const setupSteps=[
 {id:'appearance',title:'셸과 테마 선택',view:'appearance',text:'Oh My Zsh와 테마를 쓸지 정하세요. 기본 셸을 그대로 사용해도 됩니다.'},
 {id:'tools',title:'필요한 도구 선택',view:'tools',text:'이동·검색·언어 도구 중 필요한 것만 켜세요. 설치 명령은 마지막 적용 단계에 나옵니다.'},
 {id:'connections',title:'원격 저장소 접근',view:'connections',text:'Git 호스트·접속 방식·인증 참조를 정하세요. 인증 참조와 키 수명은 연결 상세에서 설정하며, 접속이 필요 없으면 추가하지 않아도 됩니다.'},
 {id:'profiles',title:'커밋 작성자·적용 규칙 · 선택',view:'profiles',text:'필요한 경우 폴더 규칙을 만들고 앞에서 등록한 Git 연결을 지정하세요. 커밋 작성자 이름·이메일도 폴더별로 정할 수 있습니다. 자동 적용이 필요 없으면 이 단계는 설정 없이 확인하고 넘어가세요.'}
];
function setupSection(state,id){
 if(id==='appearance')return state.features.ohmyzsh;
 if(id==='tools')return Object.fromEntries(Object.entries(state.features).filter(([key])=>key!=='ohmyzsh'));
 if(id==='profiles')return {git:state.git,profiles:state.profiles,connection_scopes:state.connections.filter(c=>c.kind==='git'&&c.profile).map(c=>({id:c.id,profile:c.profile}))};
 if(id==='connections'){
  const connections=state.connections.filter(c=>c.kind==='git'),refs=new Set(connections.flatMap(c=>[c.credential,c.api.enabled?c.api.credential:'']).filter(Boolean));
  return {connections:connections.map(({profile,...connection})=>connection),credentials:state.credentials.filter(ref=>refs.has(ref.id)),session:connections.some(c=>c.enabled&&c.method==='ssh')?state.session:null};
 }
 return state;
}
function setupDone(id){
 if(progressSnapshot!==snapshot){progressBasis=clone(snapshot.state);progressSnapshot=snapshot;}
 return Boolean(snapshot.setup_progress?.[id]?.done)&&JSON.stringify(setupSection(draft,id))===JSON.stringify(setupSection(progressBasis,id));
}
function setupSaved(){return snapshot.revision!=='new'&&!diff(baseline,draft).length;}
function setupApplied(){return setupSaved()&&setupDone('apply')&&setupDone('shell')&&(!draft.connections.some(c=>c.enabled)||setupDone('auth'));}
function setupSummary(id){
 if(id==='appearance')return draft.features.ohmyzsh.enabled?'Oh My Zsh · '+draft.features.ohmyzsh.values.theme:'Oh My Zsh를 사용하지 않는 선택';
 if(id==='tools'){const names=snapshot.definitions.filter(f=>f.id!=='ohmyzsh'&&draft.features[f.id]?.enabled).map(f=>f.name);return names.length?names.join(', '):'추가 도구를 선택하지 않은 상태';}
 if(id==='profiles')return draft.profiles.filter(p=>p.enabled).map(p=>{const names=draft.connections.filter(c=>c.kind==='git'&&c.profile===p.id).map(c=>c.name);return p.name+' · '+p.path+' · '+(names.length?names.join(', '):'자동 적용할 연결 없음')+' · '+(draft.git.enabled?(p.author||'이름 미입력')+' / '+(p.email||'이메일 미입력'):'작성자 직접 지정 안 함')}).join('\n')||'폴더 규칙을 사용하지 않는 선택';
 return draft.connections.some(c=>c.enabled&&c.kind==='git')?draft.connections.filter(c=>c.enabled&&c.kind==='git').map(c=>c.name+' · '+c.method.toUpperCase()+' · '+c.host).join('\n'):'사용하도록 설정한 Git 연결 없음';
}
async function confirmSetup(id,done=true){
 if(recordingSetup)return;recordingSetup=true;
 try{
  const result=await api('/api/setup-progress',{step:id,completed:done,state:draft});
  snapshot.setup_progress=result.setup_progress;progressBasis=clone(draft);progressSnapshot=snapshot;
  toast(done?'진행 상황에 확인 기록을 남겼습니다.':'완료 확인을 취소했습니다.');navigate(view);
 }catch(error){toast(error.message)}finally{recordingSetup=false;}
}
function setupChecks(parent){
 if(setupSaved()){const missing=snapshot.plan.dependencies.filter(item=>!item.installed);parent.append(el('p',missing.length?'서버에서 설치 미확인: '+missing.map(item=>item.name).join(', '):'서버에서 필요한 도구 설치를 확인했습니다. 셸 적용과 인증은 아래에서 따로 확인하세요.','tool-state'));}
 parent.append(el('p','적용 명령은 이 페이지가 실행하지 않습니다. 터미널에서 실행한 뒤 아래에 직접 확인을 남기세요. 설정을 바꾸면 이 확인은 다시 필요합니다.','hint'));
 for(const [id,title,text] of [
  ['apply','configure 실행 확인','저장한 설정의 적용 안내에서 도구를 준비하고 configure 명령을 실행했습니다.'],
  ['shell','새 셸 확인','새 터미널 또는 exec zsh로 셸을 열고 선택한 설정을 확인했습니다.'],
  ['auth','Git · SSH 접속 확인','적용 안내의 인증 준비·접속 확인 명령을 실행했습니다. 이 기록은 현재 로그인 성공을 자동 검증하지 않습니다.']
 ]){
  if(id==='auth'&&!draft.connections.some(c=>c.enabled))continue;
  const done=setupDone(id),row=el('div',undefined,'setup-check');row.append(el('strong',title),el('p',text,'tool-state'));
  if(done){row.append(badge('사용자 확인 기록 있음'),button('확인 취소',()=>confirmSetup(id,false),'quiet'));const at=snapshot.setup_progress?.[id]?.completed_at;if(at)row.append(el('small',new Date(at).toLocaleString('ko-KR'),'hint'));}
  else {const action=button('실행했고 확인했어요',()=>confirmSetup(id));action.disabled=!setupSaved()||snapshot.design_preview;row.append(action);}
  parent.append(row);
 }
 if(!setupSaved())parent.append(el('p','초안을 먼저 검토·저장해야 적용 완료를 기록할 수 있습니다.','hint'));
}
function renderSetupFlow(){
 const root=$('page-body');root.replaceChildren();root.append(button('← 환경 현황',()=>navigate('overview'),'quiet'));
 const complete=[...setupSteps.map(step=>setupDone(step.id)),setupSaved(),setupApplied()],count=complete.filter(Boolean).length,next=complete.indexOf(false);
 const hero=el('section',undefined,'setup-hero');hero.append(el('span','처음 설정 · 순서와 진행 기록','setup-eyebrow'),el('h2',next<0?'기본 환경 설정을 마쳤어요':(next+1)+'. '+(setupSteps[next]?.title||(next===4?'선택한 설정 검토·저장':'도구 설치·설정 적용·접속 확인'))));
 hero.append(el('p',next<0?'아래의 외부 서비스와 프로젝트 실행 환경은 필요할 때 추가하세요.':next<4?setupSteps[next].text:next===4?'지금까지 선택한 내용을 검토하고 설정 파일을 생성하세요. 저장한 뒤 실제 환경에 적용합니다.':'적용 안내의 명령을 순서대로 실행하세요. 도구 설치, configure, 새 셸, 접속 확인이 남아 있습니다.'));
 const meter=el('progress');meter.max=6;meter.value=count;meter.setAttribute('aria-label','기본 설정 진행');hero.append(meter,el('p',count+' / 6단계 관리 설정 확인 기록 · 현재 컴퓨터의 설치 완료율이 아닙니다.','hint'));
 if(next>=0)hero.append(button(next===4?'변경 검토·적용으로 이동':'지금 할 일로 이동 →',()=>next===4?navigate('plan'):navigate(setupSteps[next]?.view||'plan'),'btn primary'));
 root.append(hero);
 const list=el('ol',undefined,'setup-list');list.setAttribute('aria-label','처음 설정 순서');root.append(list);
 for(let i=0;i<6;i++){
  const step=setupSteps[i],row=el('li',undefined,'setup-step'+(i===next?' current':''));row.dataset.setupStep=step?.id||(i===4?'save':'apply');
  const head=el('div',undefined,'between setup-step-head');head.append(el('h3',(i+1)+'. '+(step?.title||(i===4?'선택한 설정 검토·저장':'도구 설치·설정 적용·접속 확인'))),badge(complete[i]?(i<4?'선택 확인됨':i===4?'저장됨':'사용자 적용 확인'):i===next?'지금 할 일':'아직 확인 안 함'));row.append(head);
  row.append(el('p',step?setupSummary(step.id):i===4?setupSaved()?'현재 선택이 설정 파일로 저장되어 있습니다.':diff(baseline,draft).length?'저장하지 않은 변경이 있습니다.':'이 기기에 설정을 아직 저장하지 않았습니다.':'저장과 실제 적용을 구분합니다. 아래 실행 항목을 확인하세요.','tool-state'));
  if(step){row.append(button(complete[i]?'선택 다시 보기':'선택하러 가기 →',()=>navigate(step.view)));if(complete[i])row.append(button('확인 취소',()=>confirmSetup(step.id,false),'quiet'));}
  else if(i===4)row.append(button('변경 검토·적용으로 이동 →',()=>navigate('plan')));
  else row.append(el('p','변경 검토·적용에서 명령을 실행한 뒤 적용 확인을 기록합니다. 이 화면에는 그 진행 상태가 표시됩니다.','hint'),button('변경 검토·적용으로 이동 →',()=>navigate('plan')));
  list.append(row);
 }
 const optional=groupBox('기본 설정 다음 · 필요한 기능만 추가',root);
 optional.append(el('p','아래 항목은 위 6단계 진행률에 포함하지 않습니다.','hint'));
 for(const [name,destination,text] of [['외부 서비스','services','Jira·Confluence·Google 계정 로그인과 갱신'],['프로젝트 실행 환경','runtime','dev-environment 설치와 프로젝트 Dev Container 상태 확인']]){
  const row=el('div',undefined,'setup-optional');row.append(el('strong',name),el('p',text,'tool-state'),button('설정·상태 보기 →',()=>navigate(destination)));optional.append(row);
 }
 const remote=el('div',undefined,'setup-optional');remote.append(el('strong','원격 접속'),el('p','집 WSL 등 이미 준비된 개발 PC에 접속할 때만 필요합니다. 새 기기의 Tailscale 로그인 → SSH 별칭 → 접속 확인 순서로 진행합니다.','tool-state'));remote.append(button('원격 접속 준비 →',()=>navigate('servers')),el('p','설치 → 로그인 → SSH 별칭 적용 → 집 WSL 접속 확인을 단계별로 진행합니다.','hint'));optional.append(remote);
 explanation(optional,'진행 기록과 실제 상태는 다릅니다.','완료 표시는 설정 선택 또는 사용자의 실행 확인 기록입니다. 서비스 로그인·토큰 만료·컨테이너 실행을 보장하지 않습니다.');
 root.append(button('도구 설치 상태 다시 확인',refreshMetadata));
};
function attachSetupGuide(){
 if(!draft||!setupMode||['overview','setup'].includes(view)||$('setup-page-guide'))return;
 const step=setupSteps.find(item=>item.view===view);
 const root=$('page-body'),guide=el('section',undefined,'setup-page-guide');guide.id='setup-page-guide';
 guide.append(button('← 처음 설정 안내',()=>navigate('setup'),'quiet'));
 if(step){
  guide.append(el('h2',(setupSteps.indexOf(step)+1)+' / 6 · '+step.title),el('p',step.text,'tool-state'));
  const done=setupDone(step.id);guide.append(badge(done?'이 선택은 확인한 상태':'선택 후 아래 버튼으로 확인하세요'));
  const action=button(done?'선택 확인 · 다음 단계 →':'이 선택으로 진행 →',async()=>{await confirmSetup(step.id);if(setupDone(step.id)){const next=setupSteps[setupSteps.indexOf(step)+1];next?navigate(next.view):navigate('plan')}});action.disabled=snapshot.design_preview;guide.append(action);
 }else {guide.append(el('h2','처음 설정 · 필요한 기능 확인'),el('p','이 화면은 선택 기능 또는 공통 설정입니다. 처음 설정 안내에서 진행 기록을 이어갈 수 있습니다.','tool-state'));}
 root.prepend(guide);
}
const setupMark=mark;
mark=function(){setupMark();const guide=$('setup-page-guide');if(guide){guide.remove();attachSetupGuide()}};
