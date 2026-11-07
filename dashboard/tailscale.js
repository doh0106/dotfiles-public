'use strict';
labels.tailscale='Tailscale·집 WSL';
let tsData=null,tsDraft=null,tsSource=null,tsObservation=null,tsBusy=false;
async function tsRequest(request){if(['acknowledge','observe'].includes(request.action)&&!tsSaved())throw Error('바꾼 접속 설정을 먼저 저장하세요.');const response=await fetch('/api/tailscale',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const result=await response.json();if(!response.ok)throw Error(result.error);return result;}
function tsInitialize(){if(tsData)return;tsData=clone(snapshot.tailscale);tsSource=tsData.source;tsDraft=clone(tsData.target||{alias:'home-wsl',host:'',user:'',account:'',client:tsData.server_platform==='Darwin'?'macos':'linux',fingerprints:''});}
function tsSaved(){return tsData.target&&JSON.stringify(tsDraft)===JSON.stringify(tsData.target);}
function tsDraftChanged(){
 const saved=tsSaved(),steps=['install','login','ssh','connect'];
 if($('tailscale-unsaved'))$('tailscale-unsaved').hidden=Boolean(saved);
 if($('tailscale-progress'))$('tailscale-progress').textContent=(saved?steps.filter(id=>tsData.records[id]).length:0)+' / 4단계 사용자 확인 · 현재 접속 성공은 별도 시험';
 for(const [index,id] of steps.entries()){
  const status=$('ts-status-'+id),action=$('ts-confirm-'+id);
  if(status)status.textContent=saved&&tsData.records[id]?'사용자 확인 기록 있음':saved?'확인 전':'미저장 · 재확인 필요';
  if(action)action.disabled=!saved||snapshot.design_preview||(!tsData.records[id]&&steps.slice(0,index).some(prior=>!tsData.records[prior]));
 }
 all('[data-ts-step="ssh"] .ts-code,[data-ts-step="connect"] .ts-code,[data-ts-step="connect"] pre').forEach(node=>node.hidden=!saved);
}
async function tsAction(action){if(tsBusy)return;tsBusy=true;try{await action();snapshot.tailscale=clone(tsData);renderTailscale()}catch(error){toast(error.message)}finally{tsBusy=false}}
function tsCode(parent,text){const box=el('div',undefined,'ts-code');box.append(el('pre',text,'long-pre'),button('명령·설정 복사',async()=>{try{await navigator.clipboard.writeText(text);toast('복사했습니다. 안내한 클라이언트의 터미널에서 실행하세요.')}catch{toast('텍스트를 선택해 직접 복사하세요.')}}));parent.append(box);}
function tsLink(parent,text,url){const link=el('a',text+' ↗','instruction-link');link.href=url;link.target='_blank';link.rel='noopener noreferrer';parent.append(link);}
function renderTailscale(){
 tsInitialize();const root=$('page-body');root.replaceChildren();const saved=tsSaved(),steps=['install','login','ssh','connect'],records=tsData.records||{},completed=saved?steps.filter(id=>records[id]).length:0;
 const hero=el('section',undefined,'setup-hero');hero.append(el('h2','새 컴퓨터에서 집 WSL 연결하기'),el('p','이 화면은 접속할 컴퓨터를 설정합니다. 이미 구성한 집 WSL을 재설치하거나 서버 정책을 바꾸지 않습니다.'),el('p','지금 할 일: '+(!saved?'접속 대상을 준비하고 저장하세요.':completed<4?['Tailscale을 설치하세요.','같은 Tailscale 신원으로 로그인하세요.','SSH 별칭을 실제 클라이언트 설정에 적용하세요.','터미널에서 집 WSL 접속을 확인하세요.'][completed]:'4단계 확인 기록이 있습니다. 필요하면 실제 접속을 다시 시험하세요.')));const progress=el('p',completed+' / 4단계 사용자 확인 · 현재 접속 성공은 별도 시험','hint');progress.id='tailscale-progress';hero.append(progress);root.append(hero);
 const settings=groupBox('먼저 · 비공개 접속 대상 준비',root);if(tsData.error)settings.append(el('p',tsData.error,'notice'));
 settings.append(el('p','집 WSL 주소·Linux 사용자·같은 Tailscale 신원·신뢰할 공개 지문을 준비합니다. 토큰이나 개인키는 입력하지 않습니다.','tool-state'));
 const importer=el('details',undefined,'runbook-block');importer.append(el('summary','기존 비공개 dotfiles 설정 불러오기'));
 const repo=field(importer,'비공개 저장소 로컬 절대 경로','',null,null,'tailscale-private-repository');repo.placeholder='~/personal/dotfiles-private';
 const ref=field(importer,'읽을 Git ref','origin/main',[['origin/main','origin/main · 마지막 fetch 기준'],['HEAD','현재 로컬 커밋']],null,'tailscale-private-ref');
 const importButton=button('비공개 설정 불러오기',()=>tsAction(async()=>{const result=await tsRequest({action:'import',repository:repo.value,ref:ref.value});tsDraft={...result.target,client:tsDraft.client};tsSource=result.source;toast('선택한 커밋의 설정을 불러왔습니다. 검토한 뒤 저장하세요.')}));importButton.disabled=snapshot.design_preview;importer.append(importButton,el('p','로컬 Git의 정해진 WSL 설정 파일만 읽습니다. fetch·로그인·정책 적용은 실행하지 않습니다. 새 기기에서는 비공개 저장소를 먼저 받아두세요.','hint'));settings.append(importer);
 for(const [key,label] of [['client','설정할 클라이언트 OS'],['alias','SSH 별칭'],['host','집 WSL Tailscale DNS 이름 또는 IPv4'],['user','집 WSL Linux 사용자'],['account','호스트를 등록한 Tailscale 로그인 신원']]){
  const update=value=>{tsDraft[key]=value;tsSource=null;tsObservation=null;if(key==='client')renderTailscale();else tsDraftChanged();};
  const input=field(settings,label,tsDraft[key],key==='client'?[['macos','macOS'],['windows','Windows 네이티브 · PowerShell'],['linux','Linux / WSL']]:null,update,'tailscale-'+key);
  if(key!=='client')input.addEventListener('input',()=>update(input.value));
 }
 const fingerprintLabel=el('label','신뢰하는 공개 호스트 지문 · SHA256:값, 한 줄에 하나씩'),fingerprints=el('textarea');fingerprints.id='tailscale-fingerprints';fingerprintLabel.htmlFor=fingerprints.id;fingerprints.value=tsDraft.fingerprints;fingerprints.rows=4;fingerprints.addEventListener('input',()=>{tsDraft.fingerprints=fingerprints.value;tsSource=null;tsDraftChanged()});settings.append(fingerprintLabel,fingerprints);
 const dirty=el('p','접속 대상이 미저장 상태입니다. 저장 후 단계 확인을 기록할 수 있습니다.','hint');dirty.id='tailscale-unsaved';dirty.hidden=Boolean(saved);settings.append(dirty);
 const saveButton=button('접속 설정 저장 · SSH 별칭 파일 생성',()=>tsAction(async()=>{tsData=await tsRequest({action:'save',target:tsDraft,source:tsSource,revision:tsData.revision});tsDraft=clone(tsData.target);tsSource=tsData.source;tsObservation=null;toast('전용 설정과 SSH 별칭 파일을 저장했습니다. 이미 Include를 적용했다면 새 별칭 내용이 반영됩니다. 로그인은 실행하지 않았습니다.')}),'btn primary');saveButton.disabled=snapshot.design_preview;settings.append(saveButton);
 if(tsSource)settings.append(el('p','비공개 출처: '+tsSource.ref+' · '+tsSource.commit.slice(0,12)+' · '+tsSource.imported_at+' (저장된 기록이며 현재 호스트 검증 아님)','hint'));
 settings.append(el('p','저장 위치: '+tsData.config_path+' · 선택한 주소·지문·OS가 바뀌면 4단계 확인을 다시 진행합니다.','hint'));
 if(tsData.server_wsl)settings.append(el('p','현재 대시보드는 WSL에서 실행 중입니다. Windows 앱용 접속은 Windows의 Tailscale과 SSH 설정을 사용하세요. Windows와 WSL에 중복 설치하지 않습니다.','notice'));
 const titles={install:'Tailscale 설치',login:'같은 계정으로 로그인',ssh:'SSH 별칭 적용',connect:'집 WSL에 실제 접속 확인'};
 for(const [index,id] of steps.entries()){
  const box=groupBox((index+1)+'. '+titles[id],root);
  box.parentElement.dataset.tsStep=id;const status=badge(saved&&records[id]?'사용자 확인 기록 있음':'확인 전');status.id='ts-status-'+id;box.append(status);
  if(id==='install'){
   if(tsDraft.client==='macos'){box.append(el('p','macOS용 Standalone 패키지를 설치하고 Tailscale 앱을 여세요. OS가 네트워크 확장 권한을 요청하면 설치 안내에 따라 허용합니다. 이미 설치되어 있다면 다시 설치하지 마세요.','tool-state'));tsLink(box,'공식 macOS 설치 파일','https://tailscale.com/download/mac');box.append(el('p','CLI를 쓸 경우 앱 설정의 CLI integration을 활성화하세요. GUI 설치가 되어 있어도 서버 PATH에서 CLI를 못 찾을 수 있습니다.','hint'));}
   else if(tsDraft.client==='windows'){box.append(el('p','Windows용 설치 프로그램을 실행한 뒤 시작 메뉴에서 Tailscale을 여세요. Windows용 앱으로 SSH 접속할 때는 Windows에 설치합니다.','tool-state'));tsLink(box,'공식 Windows 설치 파일','https://tailscale.com/download/windows');}
   else{box.append(el('p','실제로 SSH를 실행할 Linux/WSL 배포판에 설치합니다. 공식 Linux 설치 안내에서 배포판에 맞는 패키지 명령을 실행하고 tailscaled 서비스를 시작하세요. Windows 클라이언트가 이미 담당하는 연결이면 Windows를 선택하세요.','tool-state'));tsLink(box,'배포판별 공식 설치 명령','https://tailscale.com/docs/install/linux');}
  }
  if(id==='login'){
   box.append(el('p','Tailscale 앱의 Log in을 누르고 집 WSL을 등록한 것과 같은 신원으로 로그인하세요. 새 컴퓨터는 각각 등록해야 합니다. 로그인·MFA·OS 권한 요청은 직접 완료합니다.','tool-state'),el('p','예상 신원: '+(tsDraft.account||'위에서 입력하세요'),'hint'));
   if(tsDraft.client==='linux')tsCode(box,'sudo systemctl enable --now tailscaled\nsudo tailscale up');
   box.append(button('이 서버의 설치·로그인 상태 확인',()=>tsAction(async()=>{tsObservation=await tsRequest({action:'observe'})})));
   if(tsObservation){const messages={different_client_os:'선택한 OS와 서버 OS가 달라 확인할 수 없습니다. 선택한 클라이언트에서 직접 확인하세요.',cli_not_found:'서버에서 CLI를 찾지 못했습니다. 앱 설치 또는 CLI integration을 확인하세요.',not_running:'Tailscale이 Running 상태가 아닙니다. 앱의 로그인과 연결을 확인하세요.',unavailable:'상태를 읽지 못했습니다. 앱 또는 같은 터미널에서 tailscale status를 확인하세요.',running:'서버에서 Tailscale Running을 확인했습니다.'};box.append(el('p',messages[tsObservation.status]||'미확인','tool-state'));if(tsObservation.status==='running')box.append(el('p','현재 신원: '+(tsObservation.account||'읽기 실패')+' · '+(tsObservation.account_matches?'예상 신원과 일치':'예상 신원과 불일치 또는 미확인'),'hint'));box.append(el('p','조회 시각: '+tsObservation.observed_at+' · 서버 프로세스 범위, SSH 접속 검증 아님','hint'));}
  }
  if(id==='ssh'){
   box.append(el('p','저장은 전용 SSH 별칭 파일을 생성합니다. Include가 이미 연결되어 있으면 저장한 내용이 바로 반영됩니다. 처음에는 아래 절차로 실제 클라이언트의 SSH 설정에 연결하세요. 기존 같은 별칭이 있으면 값을 비교해 중복을 정리하세요. 개인키를 복사하거나 authorized_keys를 바꾸지 않습니다.','tool-state'));
   if(saved){tsCode(box,tsData.ssh_config);if(tsDraft.client==='windows'){box.append(el('p','Windows PowerShell에서 아래 경로를 열고 위 Host 블록을 기존 설정과 병합하세요. WSL의 ~/.ssh/config와는 별개입니다.','tool-state'));tsCode(box,'New-Item -ItemType Directory -Force "$env:USERPROFILE\\.ssh"\nnotepad "$env:USERPROFILE\\.ssh\\config"');}else if((tsDraft.client==='macos'&&tsData.server_platform==='Darwin')||(tsDraft.client==='linux'&&tsData.server_platform==='Linux')){box.append(el('p','기존 dotfiles configure에도 이 Include를 연결했습니다. SSH 설정만 적용하려면 다음 명령을 실행하세요. 기존 SSH 설정은 보존·백업합니다.','tool-state'));tsCode(box,snapshot.tailscale_apply_command);}else box.append(el('p','선택한 OS와 이 서버의 OS가 다릅니다. 접속할 Mac/Linux의 ~/.ssh/config에 위 블록을 병합하거나, 그 기기에서 대시보드를 실행해 SSH 적용 명령을 사용하세요.','hint'));}
   else box.append(el('p','접속 설정을 저장하면 정확한 SSH 블록과 적용 명령이 나옵니다.','hint'));
  }
  if(id==='connect'){
   box.append(el('p','집 PC가 켜져 있고 Windows 사용자 로그인을 마쳤는지 확인하세요. 선택한 클라이언트의 터미널에서 아래 명령으로 접속합니다.','tool-state'));
   if(saved){tsCode(box,'ssh '+tsData.target.alias);box.append(el('p','처음 연결할 때 SSH가 제시한 SHA256 지문을 아래의 신뢰하는 기록과 대조하세요. 일치할 때만 수락합니다. 불일치하면 멈추고 집 PC에서 지문을 다시 확인하세요.','tool-state'));box.append(el('pre',tsData.target.fingerprints,'long-pre'));box.append(el('p','로그인되면 원격 셸에서 아래 명령을 실행하세요. Linux 사용자명이 '+tsData.target.user+'이고 집 WSL 호스트가 맞는지 확인한 뒤 종료합니다.','tool-state'));tsCode(box,'id -un\nhostname\nexit');}
   box.append(el('p','재인증 창이 나오면 같은 신원으로 완료하세요. 실패하면 클라이언트 신원 → 집 PC/WSL 실행 → tailnet 접근·SSH 정책 → 실제 앱의 SSH 설정 순서로 확인합니다. 기존 SSH 2222번 경로는 이 22번 Tailscale SSH 접속과 별개입니다.','hint'));
  }
  const done=saved&&records[id],action=button(done?'이 단계 확인 취소':'이 단계를 직접 완료했어요',()=>tsAction(async()=>{tsData=await tsRequest({action:'acknowledge',step:id,completed:!done,revision:tsData.revision});toast('사용자 확인 기록을 저장했습니다. 현재 인증 성공을 자동 판정한 것은 아닙니다.')}));
  action.id='ts-confirm-'+id;action.disabled=!saved||snapshot.design_preview||(!done&&steps.slice(0,index).some(prior=>!records[prior]));box.append(action);
  if(done)box.append(el('p','사용자 확인: '+new Date(records[id].checked_at).toLocaleString('ko-KR'),'hint'));
 }
 const finish=groupBox('접속이 되면 · 원격 작업 시작',root);finish.append(el('p','터미널 SSH 성공을 먼저 확인한 뒤 사용하는 원격 개발 앱에서 이 별칭과 프로젝트 폴더를 선택하세요. 앱별 접속 성공은 따로 확인합니다.','tool-state'));
 tsLink(finish,'기존 비공개 호스트·복구 안내','https://github.com/doh0106/dotfiles/tree/main/docs/wsl-remote-access');
}
window.addEventListener('beforeunload',event=>{if(tsDraft&&tsData&&JSON.stringify(tsDraft)!==JSON.stringify(tsData.target||{alias:'home-wsl',host:'',user:'',account:'',client:tsData.server_platform==='Darwin'?'macos':'linux',fingerprints:''})){event.preventDefault();event.returnValue=''}});
