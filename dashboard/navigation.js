'use strict';
// Navigation owns presentation only. Settings, credentials and progress keep their owners.
let setupMode=false;
const domains=[
 {id:'apps',title:'앱·도구',icon:'shell',start:'appearance',intro:'필요한 프로그램을 준비하고 터미널·셸과 AI 작업 도구를 설정합니다.',pages:[['appearance','터미널·셸·테마'],['tools','프로그램 설치'],['agents','AI 도구·스킬']]},
 {id:'git',title:'Git',icon:'git',start:'connections',intro:'서버별로 clone·pull·push에 사용할 접속 방식과 인증을 설정합니다. 커밋 작성자와 폴더 규칙도 따로 관리할 수 있습니다.',pages:[['connections','원격 저장소 접근'],['profiles','커밋 작성자·적용 규칙 · 선택']]},
 {id:'remote',title:'원격 접속',icon:'globe',start:'servers',intro:'터미널로 접속할 컴퓨터를 등록하고 SSH와 필요한 네트워크 연결을 준비합니다.',pages:[['servers','SSH 접속 대상'],['key-supply','SSH agent'],['tailscale','Tailscale·집 WSL']]},
 {id:'credentials',title:'비밀 관리',icon:'key',start:'providers',intro:'Bitwarden 연결과 등록된 값의 공급을 관리합니다. 보관 항목의 생성·편집은 Bitwarden에서, SSH agent는 원격 접속에서 관리합니다.',pages:[['providers','Bitwarden 연결 설정'],['secret-keys','SSH 키 가져오기·공급'],['secret-tokens','환경변수 공급']]},
 {id:'runtime',title:'프로젝트 실행 환경',icon:'code',start:'runtime',intro:environmentViews.runtime[1],pages:[['runtime','프로젝트 실행 환경']]},
 {id:'services',title:'외부 서비스',icon:'link',start:'services',intro:environmentViews.services[1],pages:[['services','외부 서비스']]}
];
Object.assign(labels,{existing:'기존 설정 가져오기',overview:'내 환경',plan:'변경 검토·적용',setup:'처음 설정',agents:'AI 도구·스킬',servers:'SSH 접속 대상','remote-secrets':'인증정보 참조 관리','remote-sessions':'SSH 키·세션 정책',runtime:'프로젝트 실행 환경',services:'외부 서비스',tools:'프로그램 설치',appearance:'터미널·셸·테마',profiles:'커밋 작성자·적용 규칙',connections:'원격 저장소 접근','key-supply':'SSH agent','secret-keys':'SSH 키 가져오기·공급',secrets:'SSH 키 공급','secret-tokens':'환경변수 공급',passwords:'SSH 키 공급',providers:'Bitwarden 연결 설정','secret-links':'공급·연동',sessions:'키·세션 정책'});
function domainFor(page){return domains.find(domain=>[...domain.pages,...(domain.utilities||[])].some(([id])=>id===page));}
function primaryButton(title,id,icon){const item=button(title,()=>navigate(id,{primary:true}));item.dataset.view=id;item.setAttribute('aria-label',title);item.disabled=!draft;if(icon)item.insertAdjacentHTML('afterbegin',svg[icon]);return item;}
function buildNavigation(){
 const nav=document.querySelector('.nav');nav.replaceChildren(primaryButton('내 환경','overview','code'),primaryButton('변경 검토·적용','plan','git'));const pending=el('span','0','badge');pending.dataset.changeCount='';pending.hidden=true;nav.querySelector('[data-view=plan]').append(pending);
 const group=el('div',undefined,'nav-domain-group');group.setAttribute('role','group');group.setAttribute('aria-label','환경 구성');group.append(el('div','환경 구성','navlabel'));
 for(const domain of domains)group.append(primaryButton(domain.title,domain.start,domain.icon));nav.append(group);
 const help=el('div',undefined,'nav-domain-group');help.append(el('div','시작 안내','navlabel'),primaryButton('처음 설정','setup','help'));nav.append(help);
 const mobile=$('mobile-nav');mobile.replaceChildren();
 for(const [id,title] of [['overview','내 환경'],['plan','변경 검토·적용']]){const option=el('option',title);option.value=id;mobile.append(option)}
 const options=el('optgroup');options.label='환경 구성';for(const domain of domains){const option=el('option',domain.title);option.value=domain.start;options.append(option)}mobile.append(options);
 const start=el('optgroup');start.label='시작 안내';const option=el('option','처음 설정');option.value='setup';start.append(option);mobile.append(start);
 mobile.onchange=event=>navigate(event.target.value,{primary:true});$('about-link').textContent='기존 설정 가져오기';$('about-link').onclick=event=>{event.preventDefault();navigate('existing',{primary:true})};
}
function updateLocation(){
 const domain=domainFor(view),primary=setupMode?'setup':domain?.start||(['plan','setup'].includes(view)?view:'overview');
 all('.nav [data-view]').forEach(item=>{const active=item.dataset.view===primary;item.classList.toggle('active',active);active?item.setAttribute('aria-current','page'):item.removeAttribute('aria-current')});$('mobile-nav').value=primary;
 const step=setupSteps.find(item=>item.view===view);
 $('breadcrumb').textContent=setupMode&&view!=='setup'?'처음 설정 / '+(step?(setupSteps.indexOf(step)+1)+'. ':'')+labels[view]:domain?'환경 구성 / '+domain.title+(domain.title!==labels[view]?' / '+labels[view]:''):view==='existing'?'환경 현황 / 기존 설정 가져오기':labels[view];
 $('page-title').textContent=labels[view];document.title=labels[view]+' · dotfiles';
 $('overline').textContent=setupMode?'처음 설정 안내':domain?'환경 구성 · '+domain.title:view==='plan'?'변경 관리':view==='existing'?'기존 설정 가져오기':'내 환경';
 $('page-intro').textContent=view==='key-supply'?'준비된 개인키를 등록하고 agent 소켓·키 유지 시간·해제를 관리합니다. 비밀 저장소에 연결할 필요는 없습니다.':view==='secret-keys'?'비밀 저장소에서 SSH 키를 준비해 선택한 agent에 공급합니다. agent 자체의 설정은 원격 접속에서 관리합니다.':domain?.intro||({overview:'설치·설정 적용을 진행하고 필요한 인증과 업데이트를 이어갑니다.',setup:'새 컴퓨터에서 설정을 가져오고 설치·인증을 이어가는 순서입니다.',existing:'감지한 설정을 검토하고 원본을 유지하는 참조로 관리 목록에 추가합니다.',plan:'셸·도구·Git·SSH 설정의 변경을 검토·저장하고 적용 방법을 확인합니다. 서비스 로그인과 프로젝트 실행은 각 화면에서 진행합니다.'})[view];
 const action=({connections:'+ Git 연결 추가',servers:'+ SSH 대상 추가',profiles:'+ 폴더 규칙 추가','remote-secrets':'+ 인증 참조 추가'})[view];$('heading-action').hidden=!action;$('heading-action').textContent=action||'';
}
function attachDomainNavigation(){
 if(!draft)return;
 const root=$('page-body'),domain=domainFor(view);
 if(domain?.pages.length>1&&!$('domain-navigation')){
  const tabs=el('nav',undefined,'domain-navigation');tabs.id='domain-navigation';tabs.setAttribute('aria-label',domain.title+' 세부 설정');
  for(const [id,title] of domain.pages){const item=button(title,()=>navigate(id),id===view?'btn active':'btn');if(id===view)item.setAttribute('aria-current','page');tabs.append(item)}
  if(domain.utilities){
   const extra=el('details',undefined,'domain-utilities');extra.id='domain-utilities';extra.open=domain.utilities.some(([id])=>id===view);
   extra.append(el('summary','고급 설정'),el('p','인증 참조와 키 수명은 연결 상세에서도 설정할 수 있습니다. 이 메뉴는 공통 설정을 모아보는 곳이며 처음 설정의 별도 단계가 아닙니다.','hint'));
   for(const [id,title] of domain.utilities)extra.append(button(title,()=>navigate(id),id===view?'btn active':'btn'));
   tabs.append(extra);
  }
  root.prepend(tabs);
 }
 attachExistingSummary();
 attachSetupGuide();
}
const rootRoutes={overview:'status',plan:'changes',setup:'start',existing:'existing-settings'};
function routeFor(page){const domain=domainFor(page);return '#/'+(setupMode&&page!=='setup'?'start/'+page:rootRoutes[page]||(domain?domain.pages.length===1&&page===domain.start?domain.id:domain.id+'/'+page:page));}
function restoreDashboardLocation(){
 const path=location.hash.replace(/^#\//,''),root=Object.keys(rootRoutes).find(key=>rootRoutes[key]===path);
 if(path.startsWith('start/')&&Object.hasOwn(labels,path.slice(6))){setupMode=true;navigate(path.slice(6),{history:false});return}
 const page=path.split('/').pop();setupMode=false;navigate(root||Object.hasOwn(labels,page)&&page||'overview',{history:false});
}
function navigate(next,options={}){
 if(!draft)return;
 for(const dialog of all('dialog[open]'))dialog.close();
 if(next==='passwords')next='providers';if(next==='secrets')next='secret-keys';
 if(next==='remote-secrets'||next==='sessions'||next==='remote-sessions')next='key-supply';if(next==='secret-links')next='connections';
 if(next==='environment')next='services';const domain=domains.find(item=>item.id===next);if(domain)next=domain.start;
 if(options.primary)setupMode=false;if(next==='setup')setupMode=true;if(['overview','plan','existing'].includes(next))setupMode=false;
 const renders={overview:renderEnvironmentOverview,setup:renderStartGuide,existing:renderExistingSettings,tools:renderTools,appearance:renderAppearance,agents:renderAgents,connections:renderConnections,servers:renderConnections,profiles:renderProfiles,'key-supply':renderAgentManager,'secret-keys':renderSecretSshWorkflow,secrets:renderSecrets,providers:renderProviders,'secret-tokens':renderSecretTokenWorkflow,'secret-links':renderSecretLinks,sessions:renderSessions,'remote-secrets':renderSecrets,'remote-sessions':renderSessions,services:renderEnvironment,runtime:renderEnvironment,tailscale:renderTailscale,plan:renderPlan};
 if(!renders[next])next='overview';const changed=view!==next||location.hash!==routeFor(next);
 if(['connections','servers'].includes(next)&&view!==next){chosen='';search='';}
 view=next;const hash=routeFor(view);if(location.hash!==hash){if(options.history===false||!location.hash)history.replaceState(null,'',hash);else history.pushState(null,'',hash)}
 updateLocation();renders[view]();mark();attachDomainNavigation();
 if(changed){$('page-title').tabIndex=-1;$('page-title').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'})}
}
window.addEventListener('popstate',()=>{if(draft)restoreDashboardLocation()});

function renderEnvironmentOverview(){renderControlCenter()}
function instructionLink(parent,title,url){const link=el('a',title+' ↗','instruction-link');link.href=url;link.target='_blank';link.rel='noopener noreferrer';parent.append(link);}
function renderAgents(){
 const root=$('page-body');root.replaceChildren();
 const tools=groupBox('AI 도구 준비',root);tools.append(el('p','프로그램 설치에서 필요한 AI 도구를 선택하고 저장한 뒤 적용 안내를 실행하세요. 도구별 계정 로그인은 설치 후 진행합니다.','tool-state'));
 for(const definition of snapshot.definitions.filter(item=>item.category==='ai')){const row=el('div',undefined,'settingrow');row.append(el('span',definition.name),badge(definition.installed?'설치됨':'설치 미확인'));tools.append(row)}
 tools.append(button('프로그램 선택·설치 안내 →',()=>navigate('tools')));
 const skills=groupBox('Agent Kit 스킬',root);skills.append(el('p','사용할 AI 도구를 준비한 뒤 필요한 스킬 묶음을 설치하세요. 스킬 설치와 Jira·Google 등의 계정 연결은 별도로 진행합니다.','tool-state'));
 instructionLink(skills,'도구별 설치 안내','https://github.com/dohyun-ignite/agent-kit#readme');
 instructionLink(skills,'목적별 스킬 묶음과 구성','https://github.com/dohyun-ignite/agent-kit/blob/main/docs/agent-kit-structure.md');
 skills.append(el('p','이 화면에서는 도구 안에 설치된 스킬의 버전·활성 상태를 자동 조회하지 않습니다. 설치 후 사용하는 AI 도구에서 확인하세요.','hint'));
 const connection=groupBox('작업에 필요한 외부 서비스',root);connection.append(el('p','Jira·Confluence·Google 연결은 외부 서비스에서 준비합니다. 인증 관리 화면을 사용하기 위해 Agent Kit을 먼저 설치할 필요는 없습니다.','tool-state'),button('외부 서비스 설정 →',()=>navigate('services')));
}
buildNavigation();
new MutationObserver(attachDomainNavigation).observe($('page-body'),{childList:true});
initializeDashboard();
