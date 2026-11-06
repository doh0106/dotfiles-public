'use strict';
// Setup acknowledgements are per-machine metadata, never proof of a live login.
labels.overview='처음 설정 · 진행 상황';
let progressBasis=null,progressSnapshot=null,recordingSetup=false;
const setupSteps=[
 {id:'appearance',title:'셸과 테마 선택',view:'appearance',text:'Oh My Zsh와 테마를 쓸지 정하세요. 기본 셸을 그대로 사용해도 됩니다.'},
 {id:'tools',title:'필요한 도구 선택',view:'tools',text:'이동·검색·언어 도구 중 필요한 것만 켜세요. 설치 명령은 마지막 적용 단계에 나옵니다.'},
 {id:'profiles',title:'작업 폴더와 Git 작성자 설정',view:'profiles',text:'개인·회사 프로젝트 폴더와 Git 이름·이메일을 정하세요. Git 작성자 기능을 끄고 진행할 수도 있습니다.'},
 {id:'connections',title:'Git · SSH 접속 설정',view:'connections',text:'Git 호스트·SSH 서버의 접속 방식과 키·토큰의 보관 위치를 지정하세요. 접속이 필요 없으면 추가하지 않아도 됩니다.'}
];
function setupSection(state,id){
 if(id==='appearance')return state.features.ohmyzsh;
 if(id==='tools')return Object.fromEntries(Object.entries(state.features).filter(([key])=>key!=='ohmyzsh'));
 if(id==='profiles')return {git:state.git,profiles:state.profiles};
 if(id==='connections')return {git:state.git,profiles:state.profiles,connections:state.connections,credentials:state.credentials,session:state.session};
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
 if(id==='profiles')return draft.git.enabled?draft.profiles.filter(p=>p.enabled).map(p=>p.name+' · '+p.path+' · '+(p.author||'이름 미입력')+' / '+(p.email||'이메일 미입력')).join('\n'):'폴더별 Git 작성자 기능 꺼짐';
 return draft.connections.some(c=>c.enabled)?draft.connections.filter(c=>c.enabled).map(c=>c.name+' · '+c.method.toUpperCase()+' · '+c.host).join('\n'):'사용할 Git · SSH 접속이 아직 없음';
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
renderOverview=function(){
 const root=$('page-body');root.replaceChildren();
 const complete=[...setupSteps.map(step=>setupDone(step.id)),setupSaved(),setupApplied()],count=complete.filter(Boolean).length,next=complete.indexOf(false);
 const hero=el('section',undefined,'setup-hero');hero.append(el('span','처음 사용하는 기기 설정','setup-eyebrow'),el('h2',next<0?'기본 환경 설정을 마쳤어요':(next+1)+'. '+(setupSteps[next]?.title||(next===4?'선택한 설정 검토·저장':'도구 설치·설정 적용·접속 확인'))));
 hero.append(el('p',next<0?'아래의 서비스 인증과 컨테이너 개발 환경은 필요할 때 추가하세요.':next<4?setupSteps[next].text:next===4?'지금까지 선택한 내용을 검토하고 설정 파일을 생성하세요. 저장한 뒤 실제 환경에 적용합니다.':'적용 안내의 명령을 순서대로 실행하세요. 도구 설치, configure, 새 셸, 접속 확인이 남아 있습니다.'));
 const meter=el('progress');meter.max=6;meter.value=count;meter.setAttribute('aria-label','기본 설정 진행');hero.append(meter,el('p',count+' / 6단계 확인 · 실제 적용은 별도 확인','hint'));
 if(next>=0)hero.append(button(next===4?'변경 검토 · 저장하기':'지금 할 일로 이동 →',()=>next===4?review():navigate(setupSteps[next]?.view||'plan'),'btn primary'));
 root.append(hero);
 const list=el('ol',undefined,'setup-list');list.setAttribute('aria-label','처음 설정 순서');root.append(list);
 for(let i=0;i<6;i++){
  const step=setupSteps[i],row=el('li',undefined,'setup-step'+(i===next?' current':''));row.dataset.setupStep=step?.id||(i===4?'save':'apply');
  const head=el('div',undefined,'between setup-step-head');head.append(el('h3',(i+1)+'. '+(step?.title||(i===4?'선택한 설정 검토·저장':'도구 설치·설정 적용·접속 확인'))),badge(complete[i]?(i<4?'선택 확인됨':i===4?'저장됨':'사용자 적용 확인'):i===next?'지금 할 일':'아직 확인 안 함'));row.append(head);
  row.append(el('p',step?setupSummary(step.id):i===4?setupSaved()?'현재 선택이 설정 파일로 저장되어 있습니다.':diff(baseline,draft).length?'저장하지 않은 변경이 있습니다.':'이 기기에 설정을 아직 저장하지 않았습니다.':'저장과 실제 적용을 구분합니다. 아래 실행 항목을 확인하세요.','tool-state'));
  if(step){row.append(button(complete[i]?'선택 다시 보기':'선택하러 가기 →',()=>navigate(step.view)));if(complete[i])row.append(button('확인 취소',()=>confirmSetup(step.id,false),'quiet'));}
  else if(i===4)row.append(button('변경 검토 · 저장',review));
  else {row.append(button('적용 안내 열기 →',()=>navigate('plan')));setupChecks(row);}
  list.append(row);
 }
 const optional=groupBox('기본 설정 다음 · 필요한 기능만 추가',root);
 optional.append(el('p','아래 항목은 위 6단계 진행률에 포함하지 않습니다.','hint'));
 for(const [name,destination,text] of [['서비스 인증','services','Jira·Confluence·Google 계정 로그인과 갱신'],['컨테이너 개발 환경','runtime','dev-environment 설치와 프로젝트 Dev Container 상태 확인']]){
  const row=el('div',undefined,'setup-optional');row.append(el('strong',name),el('p',text,'tool-state'),button('설정·상태 보기 →',()=>navigate(destination)));optional.append(row);
 }
 const remote=el('div',undefined,'setup-optional');remote.append(el('strong','원격 개발 PC 연결 · Tailscale'),el('p','집 WSL 등 이미 준비된 개발 PC에 접속할 때만 필요합니다. 새 기기의 Tailscale 로그인 → SSH 별칭 → 접속 확인 순서로 진행합니다.','tool-state'));const remoteLink=el('a','비공개 저장소의 새 컴퓨터 연결 안내 ↗','instruction-link');remoteLink.href='https://github.com/doh0106/dotfiles/blob/main/docs/wsl-remote-access/docs/new-client.md';remoteLink.target='_blank';remoteLink.rel='noopener noreferrer';remote.append(button('Tailscale 설정 시작 →',()=>navigate('tailscale')),el('p','설치 → 로그인 → SSH 별칭 적용 → 집 WSL 접속 확인을 단계별로 진행합니다.','hint'));optional.append(remote);
 explanation(optional,'진행 기록과 실제 상태는 다릅니다.','완료 표시는 설정 선택 또는 사용자의 실행 확인 기록입니다. 서비스 로그인·토큰 만료·컨테이너 실행을 보장하지 않습니다.');
 root.append(button('도구 설치 상태 다시 확인',refreshMetadata));
};
function attachSetupGuide(){
 if(!draft||view==='overview'||$('setup-page-guide'))return;
 const step=setupSteps.find(item=>item.view===view);if(!step&&view!=='plan')return;
 const root=$('page-body'),guide=el('section',undefined,'setup-page-guide');guide.id='setup-page-guide';
 guide.append(button('← 처음 설정 · 진행 상황',()=>navigate('overview'),'quiet'));
 if(step){
  guide.append(el('h2',(setupSteps.indexOf(step)+1)+' / 6 · '+step.title),el('p',step.text,'tool-state'));
  const done=setupDone(step.id);guide.append(badge(done?'이 선택은 확인한 상태':'선택 후 아래 버튼으로 확인하세요'));
  const action=button(done?'선택 확인 · 다음 단계 →':'이 선택으로 진행 →',async()=>{await confirmSetup(step.id);if(setupDone(step.id)){const next=setupSteps[setupSteps.indexOf(step)+1];next?navigate(next.view):review()}});action.disabled=snapshot.design_preview;guide.append(action);
 }else {guide.append(el('h2','6 / 6 · 명령 실행 후 확인'),el('p','위에서 저장한 설정을 아래 명령으로 적용합니다. 실행이 끝나면 여기에 확인을 남기세요.','tool-state'));setupChecks(guide);}
 root.prepend(guide);
}
const setupNavigate=navigate;
navigate=function(next){setupNavigate(next);attachSetupGuide()};
new MutationObserver(()=>attachSetupGuide()).observe($('page-body'),{childList:true});

const setupMark=mark;
mark=function(){setupMark();const guide=$('setup-page-guide');if(guide){guide.remove();attachSetupGuide()}};
