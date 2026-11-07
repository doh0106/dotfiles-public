'use strict';
// Optional integration; existing configuration and Git authentication remain independent.
const environmentViews={
 services:['외부 서비스','Jira·Confluence·Google 계정의 설정 상태를 확인하고 별도 창에서 로그인·갱신·검증합니다.'],
 runtime:['프로젝트 실행 환경','프로젝트의 Dev Container 구성과 컨테이너 상태를 확인합니다. 생성·접속·중지는 dev-* 명령으로 진행합니다.']
};
async function environmentRequest(body){
 const response=await fetch('/api/environment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const result=await response.json();if(!response.ok)throw Error(result.error);return result;
}
function renderEnvironment(observation=snapshot.shared_environment){
 const root=$('page-body');root.replaceChildren();
 const state=observation||{availability:'unavailable'};
 if(view==='services'){
 const box=groupBox('계정 연결·인증·사용 설정',root);
 if(state.availability!=='available'){
  box.append(el('p','서비스 인증 관리 모듈이 준비되지 않았습니다. 설치·연결 안내를 확인하세요.','tool-state'));
  explanation(box,'서비스 인증 준비','environment-core 설치·연결 후 대시보드를 다시 여세요. 자세한 절차는 저장소의 docs/environment-control.md를 확인하세요.');
 }else{
  box.append(el('p','관측 시각: '+new Date(state.observed_at).toLocaleString('ko-KR')+' · 로컬 설정·파일 메타데이터','hint'));
  for(const item of state.connections||[]){
   const row=el('div',undefined,'settingrow');
   const text=el('span',({jira:'Jira',confluence:'Confluence',google:'Google'})[item.product]||item.product);text.append(el('small',item.site||item.account||'서비스별 계정 설정'));
   const statuses={configured_unverified:'설정됨 · 현재 인증 미검증',not_configured:'미설정',missing:'미설정',invalid:'설정 확인 필요'};
   row.append(text,badge(statuses[item.status]||'미확인'));box.append(row);
   if(item.last_check?.checked_at)box.append(el('p','마지막 검증: '+item.last_check.checked_at+' · 현재 연결 성공을 보장하지 않습니다.','hint'));
  }
  box.append(button('서비스 연결·인증 설정 열기',async()=>{try{const result=await environmentRequest({action:'open_services'});toast(result.status==='already_running'?'이미 열린 서비스 설정 창을 확인하세요.':'서비스 설정 창 열기를 요청했습니다. 연결 성공은 해당 창에서 확인하세요.')}catch(error){toast(error.message)}}));
  explanation(box,'별도 서비스 설정 창','현재 대시보드가 실행한 설정 서버는 대시보드 종료 시 함께 종료합니다. 토큰은 서비스 설정 창의 전용 입력란에서만 다룹니다.');
 }
 const tools=groupBox('연결에 필요한 프로그램',root);tools.append(el('p','서비스별 설정 창에서 선택한 인증 방식에 필요한 도구를 확인하세요. 공통 프로그램 선택과 설치 안내는 앱·도구에서도 볼 수 있습니다.','tool-state'),button('앱·도구 열기 →',()=>navigate('tools')));
 return;
 }
 const runtime=groupBox('Dev Container 상태',root);
 if(state.availability!=='available')runtime.append(el('p','개발 환경 상태를 읽을 공통 모듈이 준비되지 않았습니다. 설치·연결 안내를 확인하세요.','tool-state'));
 const row=el('div',undefined,'field'),label=el('label','프로젝트 절대 경로'),input=el('input');
 input.id='environment-workspace';input.type='text';label.htmlFor=input.id;input.placeholder='/path/to/project';input.value=state.environment?.workspace||'';row.append(label,input);runtime.append(row);
 runtime.append(button('선택한 프로젝트 상태 확인',async()=>{try{const updated=await environmentRequest({action:'observe',workspace:input.value});snapshot.shared_environment=updated;renderEnvironment(updated)}catch(error){toast(error.message)}}));
 const result=state.environment||{};
 const configurationLabels={configured:'설정됨',not_selected:'프로젝트 미선택',workspace_missing:'폴더 없음',not_configured:'프로젝트 설정 없음'};
 const runtimeLabels={not_observed:'미관측',unavailable:'실행 도구 미설치',unknown:'조회 실패',not_created:'생성되지 않음',observed:'관측 완료'};
 runtime.append(el('p','구성: '+(configurationLabels[result.configuration]||'미관측')+' · 실행: '+(runtimeLabels[result.runtime]||'미관측'),'tool-state'));
 for(const container of result.containers||[])runtime.append(el('p',container.id+' · '+container.state+' · '+container.image,'tool-state'));
 explanation(runtime,'읽기 전용 관측','Docker·컨테이너를 시작하거나 프로젝트 설정을 바꾸지 않습니다. 생성·접속·중지는 dev-environment의 기존 명령을 사용합니다.');
 const commands=groupBox('프로젝트 실행·접속·중지',root);commands.append(el('p','Docker와 Dev Container CLI, dev-environment의 공통 명령을 준비한 뒤 프로젝트 폴더의 터미널에서 실행하세요. 이 화면의 상태 확인은 컨테이너를 시작하지 않습니다.','tool-state'));
 tsCode(commands,'dev-up .     # 프로젝트 컨테이너 생성·시작\ndev-shell .  # 컨테이너 셸 접속\ndev-stats .  # 자원 사용량 확인\ndev-stop .   # 프로젝트 컨테이너 중지');
 instructionLink(commands,'공통 명령 설치와 사용 안내','https://github.com/doh0106/dev-environment#readme');
 commands.append(button('필요한 앱·도구 확인 →',()=>navigate('tools')));
}
