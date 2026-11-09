'use strict';
function renderChangeHeader(root){
 const changes=diff(baseline,draft),body=groupBox('변경 검토·저장',root);
 body.append(el('p',changes.length?'저장 전 변경 '+changes.length+'개가 있습니다. 내용을 검토한 뒤 설정 파일로 저장하세요.':snapshot.revision==='new'?'아직 직접 관리 설정을 저장하지 않았습니다. 선택한 내용을 먼저 검토하세요.':'현재 초안과 저장한 설정이 같습니다. 아래에서 적용 방법과 실행 확인을 볼 수 있습니다.','tool-state'));
 body.append(button('내 환경에서 설치·적용 →',()=>navigate('overview',{primary:true}),'btn primary'));
 body.append(button(changes.length?'변경 내용 검토·저장':'설정 내용 검토·저장',review,'btn primary'));
 explanation(body,'이 화면에서 다루는 변경','셸·도구·Git·SSH의 직접 관리 설정입니다. 기존 설정 참조는 원본을 유지하며, 외부 서비스 로그인과 프로젝트 실행·중지는 해당 화면에서 진행합니다.');
}
function renderChangeConfirmation(root){
 const body=groupBox('적용 후 확인',root);setupChecks(body);
 body.append(el('p','이 확인 기록은 처음 설정의 진행 상태에도 반영됩니다.','hint'));
}
