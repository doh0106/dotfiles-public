'use strict';
// Navigation owns presentation only. Settings, credentials and progress keep their owners.
let setupMode=false;
const domains=[
 {id:'apps',title:'앱·도구',icon:'shell',start:'tools',intro:'필요한 프로그램을 준비하고 터미널·셸과 AI 작업 도구를 설정합니다.',pages:[['tools','프로그램 설치'],['appearance','터미널·셸·테마'],['agents','AI 도구·스킬']]},
 {id:'git',title:'Git 설정',icon:'git',start:'connections',intro:'Git 호스트 접속과 폴더별 작성자 설정을 관리합니다. 두 설정은 독립적으로 사용할 수 있습니다.',pages:[['connections','Git 호스트 연결'],['profiles','작성자·적용 규칙'],['secrets','인증 참조'],['sessions','키·세션']]},
 {id:'remote',title:'원격 접속',icon:'globe',start:'servers',intro:'터미널로 접속할 컴퓨터를 등록하고 SSH와 필요한 네트워크 연결을 준비합니다.',pages:[['servers','SSH 접속 대상'],['tailscale','Tailscale·집 WSL'],['remote-secrets','인증 참조'],['remote-sessions','키·세션']]},
 {id:'runtime',title:'프로젝트 실행 환경',icon:'code',start:'runtime',intro:environmentViews.runtime[1],pages:[['runtime','프로젝트 실행 환경']]},
 {id:'services',title:'외부 서비스',icon:'link',start:'services',intro:environmentViews.services[1],pages:[['services','외부 서비스']]}
];
Object.assign(labels,{existing:'기존 설정 가져오기',overview:'환경 개요',setup:'새 컴퓨터 설정',agents:'AI 도구·스킬',servers:'SSH 접속 대상','remote-secrets':'인증 참조','remote-sessions':'키·세션',runtime:'프로젝트 실행 환경',services:'외부 서비스',tools:'프로그램 설치',appearance:'터미널·셸·테마',profiles:'작성자·적용 규칙',connections:'Git 호스트 연결',secrets:'인증 참조',sessions:'키·세션'});
function domainFor(page){return domains.find(domain=>domain.pages.some(([id])=>id===page));}
function primaryButton(title,id,icon){const item=button(title,()=>navigate(id));item.dataset.view=id;item.disabled=!draft;if(icon)item.insertAdjacentHTML('afterbegin',svg[icon]);return item;}
function buildNavigation(){
 const nav=document.querySelector('.nav');nav.replaceChildren(primaryButton('환경 개요','overview','code'));
 const group=el('div',undefined,'nav-domain-group');group.setAttribute('role','group');group.setAttribute('aria-label','환경 설정');
 group.append(el('div','환경 설정','navlabel'));
 for(const domain of domains)group.append(primaryButton(domain.title,domain.start,domain.icon));
 nav.append(group);
 const mobile=$('mobile-nav');mobile.replaceChildren();
 const overview=el('option','환경 개요');overview.value='overview';mobile.append(overview);
 const options=el('optgroup');options.label='환경 설정';
 for(const domain of domains){const option=el('option',domain.title);option.value=domain.start;options.append(option)}
 mobile.append(options);mobile.onchange=event=>navigate(event.target.value);
 $('about-link').textContent='설정 적용 안내 ↗';
}
function updateLocation(){
 const domain=domainFor(view),primary=domain?.start||'overview';
 all('.nav [data-view]').forEach(item=>{const active=item.dataset.view===primary;item.classList.toggle('active',active);active?item.setAttribute('aria-current','page'):item.removeAttribute('aria-current')});
 $('mobile-nav').value=primary;
 $('breadcrumb').textContent=domain?domain.title+(domain.pages.length>1?' / '+labels[view]:''):view==='existing'?'환경 개요 / 기존 설정 가져오기':view==='plan'?'환경 개요 / 설정 적용 안내':view==='setup'?'환경 개요 / 새 컴퓨터 설정':'환경 개요';
 $('page-title').textContent=domain?.title||labels[view];
 $('overline').textContent=view==='overview'?'MY ENVIRONMENT':view==='setup'?'GETTING STARTED':view==='plan'?'APPLY SETTINGS':view==='existing'?'EXISTING SETTINGS':'ENVIRONMENT / '+domain?.id.toUpperCase();
 $('page-intro').textContent=domain?.intro||({overview:'이 기기의 준비 상태를 확인하고, 필요한 설정부터 시작하세요.',setup:'기본 설정을 선택·저장·적용한 뒤 필요한 원격 접속과 외부 서비스를 연결하세요.',existing:'감지한 설정을 검토하고 원본을 유지하는 참조로 관리 목록에 추가합니다.',plan:'저장한 셸·도구·Git·SSH 설정을 적용하는 명령입니다. 외부 서비스의 로그인은 해당 연결 화면에서 진행하세요.'})[view];
 const action=({connections:'+ Git 연결 추가',servers:'+ SSH 대상 추가',profiles:'+ 작성자 설정 추가',secrets:'+ 인증 참조 추가','remote-secrets':'+ 인증 참조 추가'})[view];
 $('heading-action').hidden=!action;$('heading-action').textContent=action||'';
}
function attachDomainNavigation(){
 if(!draft)return;
 const root=$('page-body'),domain=domainFor(view);
 if(domain?.pages.length>1&&!$('domain-navigation')){
  const tabs=el('nav',undefined,'domain-navigation');tabs.id='domain-navigation';tabs.setAttribute('aria-label',domain.title+' 세부 설정');
  for(const [id,title] of domain.pages){const item=button(title,()=>navigate(id),id===view?'btn active':'btn');if(id===view)item.setAttribute('aria-current','page');tabs.append(item)}
  root.prepend(tabs);
 }
 attachExistingSummary();
 attachSetupGuide();
 if(domain&&!$('domain-apply-link')){
  const actions=el('div',undefined,'domain-actions');actions.id='domain-apply-link';
  if(['apps','git','remote'].includes(domain.id))actions.append(button('설정 적용 안내 →',()=>navigate('plan'),'quiet'));
  actions.append(button('환경 개요로 돌아가기',()=>navigate('overview'),'quiet'));root.append(actions);
 }
}
function navigate(next){
 if(!draft)return;
 if(next==='environment')next='services';
 const domain=domains.find(item=>item.id===next);if(domain)next=domain.start;
 if(next==='setup')setupMode=true;
 if(next==='overview')setupMode=false;
 const renders={overview:renderEnvironmentOverview,setup:renderSetupFlow,existing:renderExistingSettings,tools:renderTools,appearance:renderAppearance,agents:renderAgents,connections:renderConnections,servers:renderConnections,profiles:renderProfiles,secrets:renderSecrets,sessions:renderSessions,'remote-secrets':renderSecrets,'remote-sessions':renderSessions,services:renderEnvironment,runtime:renderEnvironment,tailscale:renderTailscale,plan:renderPlan};
 if(!renders[next])next='overview';
 if(['connections','servers'].includes(next)&&view!==next){chosen='';search='';}
 view=next;updateLocation();renders[view]();mark();attachDomainNavigation();
};
function navigationCard(parent,title,status,text,destination){
 const body=groupBox(title,parent);body.append(badge(status),el('p',text,'tool-state'),button('설정 열기 →',()=>navigate(destination)));return body;
}
function renderEnvironmentOverview(){renderInventoryOverview()}
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
