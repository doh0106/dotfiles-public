'use strict';
let existingSelection=new Set(),existingBusy=false;
const existingNames={git:'Git 작성자 규칙','git-ssh':'Git SSH 연결',ssh:'SSH 접속 대상',shell:'셸 설정'};
function hostInventory(){return snapshot.host_state||{tools:[],candidates:[],references:[],warnings:[]};}
function hostCandidates(categories){return hostInventory().candidates.filter(item=>categories.includes(item.category));}
function importedReferences(categories){return hostInventory().references.filter(item=>categories.includes(item.category));}
function referenceLabel(item){return item.category==='git'?'Git 작성자':item.label;}
function referenceStatus(item){return ({current:'원본 참조 중',changed:'원본 변경됨 · 다시 검토',missing:'원본 감지 안 됨'})[item.status]||'아직 가져오지 않음';}
function observationPair(parent,label,detected,managed){
 const block=el('div',undefined,'observation-pair');block.append(el('strong',label));
 const observed=el('div',undefined,'observed-value');observed.append(el('span','현재 감지','observation-label'),el('p',detected));
 const chosen=el('div',undefined,'managed-value');chosen.append(el('span','대시보드 관리','observation-label'),el('p',managed));block.append(observed,chosen);parent.append(block);
}
function renderInventoryOverview(){
 const root=$('page-body');root.replaceChildren();const inventory=hostInventory();
 const hero=el('section',undefined,'setup-hero');hero.append(el('span','현재 환경과 관리 설정','setup-eyebrow'),el('h2','이미 쓰는 환경부터 확인하세요'),el('p','현재 감지는 설치된 프로그램과 기존 설정을 읽은 결과입니다. 대시보드 관리는 저장한 선택과 가져온 기존 설정 참조입니다.'));
 hero.append(button('기존 설정 검토·가져오기 →',()=>navigate('existing'),'btn primary'),button('현재 상태 다시 감지',refreshHostInventory));
 if(inventory.observed_at)hero.append(el('p','감지 시각: '+new Date(inventory.observed_at).toLocaleString('ko-KR')+' · 로컬 설정 기준 · 실제 인증·접속 미검증','hint'));root.append(hero);
 const pending=diff(baseline,draft).length,management=groupBox('변경 사항',root);
 management.append(el('p',(snapshot.revision==='new'?'직접 관리 설정을 아직 저장하지 않았습니다. 기존 환경과 가져온 참조는 그대로 유지됩니다.':pending?'저장하지 않은 변경 '+pending+'개가 있습니다.':'관리 설정이 저장되어 있습니다. 실제 적용 여부는 별도로 확인하세요.'),'tool-state'));
 management.append(button('변경 검토·적용으로 이동 →',()=>navigate('plan',{primary:true})));const start=groupBox('처음 설정',root);start.append(el('p','처음 사용하는 컴퓨터의 설정 순서와 진행 기록을 확인합니다. 기존 환경을 유지하며 필요한 항목부터 진행할 수도 있습니다.','tool-state'),button('처음 설정 안내 열기 →',()=>navigate('setup',{primary:true})));
 if(pending)management.append(button('초안 변경 검토',()=>navigate('plan',{primary:true}),'btn primary'));
 const grid=el('div',undefined,'environment-grid');root.append(grid);
 const supported=snapshot.definitions.filter(item=>item.id!=='colors'),installed=supported.filter(item=>item.installed),selected=supported.filter(item=>draft.features[item.id]?.enabled);
 const apps=groupBox('앱·도구',grid),shell=hostCandidates(['shell'])[0];
 observationPair(apps,'프로그램',installed.length+'개 설치 확인 · 대시보드 도구 목록 기준',selected.length+'개 선택 · 셸 참조 '+importedReferences(['shell']).length+'개');
 apps.append(el('p',shell?'셸: '+(shell.details.theme||'기존 zsh 설정')+' · '+shell.details.resolved_source:'기존 zsh 설정이 감지되지 않았습니다.','hint'),button('앱·도구 열기 →',()=>navigate('tools')));
 const git=groupBox('Git 설정',grid);
 observationPair(git,'작성자·접속',hostCandidates(['git']).length+'개 작성자 규칙 · '+hostCandidates(['git-ssh']).length+'개 Git SSH 별칭',draft.connections.filter(item=>item.kind==='git').length+'개 직접 설정 · 기존 참조 '+importedReferences(['git','git-ssh']).length+'개');
 git.append(el('p','원격 URL·폴더 등 원본의 작성자 선택 조건을 그대로 표시합니다.','hint'),button('Git 설정 열기 →',()=>navigate('connections')));
 const remote=groupBox('원격 접속',grid),target=snapshot.tailscale?.target;
 observationPair(remote,'SSH·Tailscale',hostCandidates(['ssh']).length+'개 SSH 별칭'+(target?' · Tailscale 대상 저장됨':''),draft.connections.filter(item=>item.kind==='server').length+'개 직접 설정 · 기존 참조 '+importedReferences(['ssh']).length+'개');
 remote.append(el('p','별칭 등록과 네트워크 로그인·실제 접속 성공을 구분합니다.','hint'),button('원격 접속 열기 →',()=>navigate('servers')));
 const runtime=groupBox('프로젝트 실행 환경',grid),shared=snapshot.shared_environment;
 const commands=inventory.tools.filter(item=>['docker','devcontainer','dev-up','dev-shell'].includes(item.id)&&item.installed);
 observationPair(runtime,'실행 도구',commands.map(item=>item.name).join(' · ')||'설치 미확인',shared?.availability==='available'?'공통 모듈 연결됨 · '+(shared.environment?.workspace?'프로젝트 선택됨':'프로젝트 미선택'):'공통 모듈 미연결');
 runtime.append(el('p','도구 설치 여부입니다. 컨테이너·Docker 실행 여부는 이 감지로 판단하지 않습니다.','hint'),button('프로젝트 상태 확인 →',()=>navigate('runtime')));
 const services=groupBox('외부 서비스',grid),configured=(shared?.connections||[]).filter(item=>item.status==='configured_unverified').length;
 observationPair(services,'서비스 연결',shared?.availability==='available'?configured+'개 서비스 설정 감지 · 인증 미검증':'관리 모듈 미연결','기존 서비스 설정·인증 파일을 공통 모듈에서 참조');
 services.append(button('외부 서비스 열기 →',()=>navigate('services')));
 const extra=groupBox('공통 도구 설치 감지',root);
 const tools=el('div',undefined,'detected-tool-list');
 for(const item of inventory.tools){const line=el('span',item.name+' · '+(item.installed?'설치 감지':'미감지'),'badge'+(item.installed?' green':''));tools.append(line)}extra.append(tools,el('p','PATH 또는 지정한 앱 경로 기준입니다. 미감지는 이 서버에서 실행 파일을 찾지 못했다는 뜻입니다. 로그인 상태는 조회하지 않습니다.','hint'));
 for(const warning of inventory.warnings)root.append(el('p',warning,'hint'));
}
async function existingRequest(body){
 const response=await fetch('/api/existing-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw Error(data.error);return data;
}
async function refreshHostInventory(){
 existingSelection.clear();await refreshMetadata();
}
function candidateDetails(parent,item){
 const details=item.details;
 if(item.category==='git'){
  parent.append(el('p',(details.author||'이름 없음')+' · '+(details.email||'이메일 없음'),'tool-state'));
  const rules=el('ul',undefined,'existing-rules');for(const rule of details.conditions||[])rules.append(el('li',rule==='global'?'전역 작성자':rule));parent.append(el('strong','작성자 선택 조건'),rules);
 }else if(['ssh','git-ssh'].includes(item.category)){
  parent.append(el('p',(details.user?details.user+'@':'')+(details.hostname||details.alias)+(details.port?':'+details.port:''),'tool-state'));
  if(details.identityfile)parent.append(el('p','키 파일 참조: '+details.identityfile+' · 파일 내용은 읽지 않음','hint'));
  if(details.advanced_options||details.conditional_options)parent.append(el('p','고급 옵션·조건이 있는 설정입니다. 명령을 실행하지 않고 원본 참조를 유지합니다.','hint'));
 }else{
  parent.append(el('p','zsh · 테마 '+(details.theme||'정적 감지 안 됨'),'tool-state'));
  if(details.integration_source)parent.append(el('p','셸 구성: '+details.integration_source,'hint'));
 }
 parent.append(el('p','원본: '+item.source,'source-path'));
}
function renderExistingSettings(){
 const root=$('page-body');root.replaceChildren();const inventory=hostInventory();
 root.append(button('← 환경 현황',()=>navigate('overview'),'quiet'));
 explanation(root,'원본을 유지하는 참조로 가져옵니다.','선택한 설정의 출처와 식별자만 관리 목록에 등록합니다. Git 작성자 조건·SSH 옵션·셸 로드 순서를 바꾸거나, 키·토큰을 복사하거나, 프로그램을 설치하지 않습니다. 새 직접 관리 설정은 각 메뉴에서 따로 추가할 수 있습니다.');
 const actions=el('div',undefined,'existing-import-actions');actions.append(button('현재 상태 다시 감지',refreshHostInventory));const selected=el('span',undefined,'hint');selected.id='existing-selected-count';actions.append(selected);root.append(actions);
 const submit=button('선택한 설정을 참조로 가져오기',()=>applyExistingSelection(),'btn primary');submit.id='existing-import-submit';root.append(submit);
 function updateSelection(){selected.textContent=existingSelection.size+'개 선택';submit.disabled=existingSelection.size===0||existingBusy||snapshot.design_preview;}
 for(const [category,title] of Object.entries(existingNames)){
  const items=inventory.candidates.filter(item=>item.category===category);if(!items.length)continue;
  const group=groupBox(title+' · '+items.length+'개 감지',root);
  for(const item of items){
   const ref=inventory.references.find(record=>record.id===item.id),row=el('section',undefined,'existing-setting');row.dataset.existingId=item.id;
   const label=el('label',undefined,'existing-selection'),input=el('input');input.type='checkbox';input.value=item.id;input.checked=existingSelection.has(item.id);input.disabled=ref?.status==='current'||snapshot.design_preview;
   input.onchange=()=>{input.checked?existingSelection.add(item.id):existingSelection.delete(item.id);updateSelection()};label.append(input,document.createTextNode(referenceLabel(item)));row.append(label,badge(ref?referenceStatus(ref):'가져오기 전'));
   candidateDetails(row,item);
   if(ref)row.append(button('관리 목록에서 참조 해제',()=>removeExistingReference(item.id),'quiet'));
   group.append(row);
  }
 }
 for(const ref of inventory.references.filter(item=>item.status==='missing')){const row=groupBox(referenceLabel(ref),root);row.append(badge('원본 감지 안 됨'),el('p',ref.source,'source-path'),button('관리 목록에서 참조 해제',()=>removeExistingReference(ref.id),'quiet'))}
 if(!inventory.candidates.length)root.append(el('p','가져올 기존 설정이 감지되지 않았습니다. Git·SSH·셸 설정은 각 메뉴에서 직접 추가할 수 있습니다.','hint'));
 for(const warning of inventory.warnings)root.append(el('p',warning,'notice'));
 root.append(el('p','참조 등록은 이 기기의 existing-settings.json에 저장됩니다. 상단 변경 검토는 별도의 직접 관리 설정 초안을 저장합니다.','hint'));updateSelection();
}
async function applyExistingSelection(){
 if(existingBusy||!existingSelection.size)return;existingBusy=true;$('existing-import-submit').disabled=true;
 try{snapshot.host_state=await existingRequest({action:'import',ids:[...existingSelection],revision:hostInventory().revision});existingSelection.clear();renderExistingSettings();toast('기존 설정 참조를 관리 목록에 등록했습니다. 원본과 인증은 그대로 사용합니다.')}
 catch(error){toast(error.message)}finally{existingBusy=false;if($('existing-import-submit'))$('existing-import-submit').disabled=!existingSelection.size;}
}
async function removeExistingReference(id){
 if(existingBusy)return;existingBusy=true;
 try{snapshot.host_state=await existingRequest({action:'remove',ids:[id],revision:hostInventory().revision});existingSelection.delete(id);navigate(view);toast('관리 목록의 참조를 해제했습니다. 원본 설정은 계속 동작합니다.')}
 catch(error){toast(error.message)}finally{existingBusy=false;}
}
function attachExistingSummary(){
 const categories=({appearance:['shell'],connections:['git-ssh'],profiles:['git'],servers:['ssh']})[view];
 if(!categories||$('existing-domain-summary'))return;
 const refs=importedReferences(categories),detected=hostCandidates(categories),panel=el('section',undefined,'existing-domain-summary');panel.id='existing-domain-summary';
 const heading=el('h2','기존 설정 감지 '+detected.length+'개 · 가져온 참조 '+refs.length+'개');panel.append(heading);
 panel.append(el('p','직접 관리 설정과 별개입니다. 가져온 참조는 원본의 규칙과 인증 방식을 유지합니다.','hint'));
 for(const ref of refs){const item=detected.find(candidate=>candidate.id===ref.id),row=el('details',undefined,'existing-reference');row.append(el('summary',referenceLabel(ref)+' · '+referenceStatus(ref)));if(item)candidateDetails(row,item);else row.append(el('p',ref.source,'source-path'));panel.append(row)}
 panel.append(button('기존 설정 검토·가져오기 →',()=>navigate('existing')));
 const tabs=$('domain-navigation');if(tabs)tabs.after(panel);else $('page-body').prepend(panel);
}
