/* UI catalog mappings are design hypotheses, not confirmed user preferences. */
window.DashboardDesignManifest={
 id:'dotfiles-environment-dashboard',product:'dotfiles · 개인 환경 대시보드',
 recordType:'unverified-design-hypothesis',catalogBase:null,
 verification:'구현 동작을 별도로 확인합니다. 사용자 선호·찾기 성능은 미검증입니다.',
 defaults:{navigation:'sidebar',detail:'page',help:'expanded'},
 decisions:[
  {id:'navigation',title:'주 메뉴 위치',catalogId:'navigation-findability-primary-navigation-placement',region:'환경 현황와 앱·도구·Git·원격 접속·프로젝트 실행 환경·외부 서비스 메뉴',targetSelectors:['.sidebar'],currentVariant:'왼쪽 메뉴',
   rationale:'설정 범위를 묶어 보여주고 화면을 오가며 현재 위치를 유지하려는 설계 가설입니다.',context:'데스크톱에서 여러 환경 설정을 점검할 때',exceptions:'좁은 화면에서는 두 안 모두 기존 화면 선택 메뉴를 사용합니다. 상단 안은 줄바꿈으로 목적지를 유지합니다.',effect:'실제 메뉴 전체를 왼쪽 또는 페이지 상단에 배치합니다. 목적지와 메뉴 이름은 유지합니다.',
   controls:[{key:'navigation',type:'radio',choices:[{value:'sidebar',label:'왼쪽 메뉴'},{value:'top',label:'상단 메뉴'}]}],
   alternatives:[{label:'왼쪽 메뉴',status:'implemented',values:{navigation:'sidebar'}},{label:'상단 메뉴',status:'implemented',values:{navigation:'top'}},{label:'자주 쓰는 메뉴만 자동 노출',status:'proposal',unavailableReason:'사용 빈도 기록·정렬·숨긴 목적지 접근 규칙을 구현하지 않았습니다.'}],verification:'메뉴 이동·모바일 선택·키보드 접근을 확인했습니다. 두 배치의 탐색 성능은 비교하지 않았습니다.'},
  {id:'detail',title:'연결 목록과 상세',catalogId:'spatial-adaptive-layout-list-detail',region:'Git 호스트 또는 SSH 접속 대상 목록에서 여는 상세 화면',targetSelectors:['#page-body .inspector'],currentVariant:'목록에서 상세 열기',
   rationale:'처음에는 목록만 보고 편집할 연결을 선택한 뒤 상세를 보도록 사용자가 요청했습니다. 작업 속도에 대한 사용자 검증은 별개입니다.',context:'연결 목록에서 하나를 고르고 설정할 때',exceptions:'목록 오른쪽·아래 배치 비교는 현재 구현하지 않았습니다. 연결 상세는 목록 버튼으로 돌아갑니다.',effect:'현재 목록→상세 구조를 확인합니다. 다른 상세 배치는 아직 전환할 수 없습니다.',
   controls:[{key:'detail',type:'radio',choices:[{value:'page',label:'목록에서 상세 열기'}]}],
   alternatives:[{label:'목록에서 상세 열기',status:'implemented',values:{detail:'page'}},{label:'목록 오른쪽',status:'proposal',unavailableReason:'새 목록→상세 흐름에 병렬 편집 영역을 구현하지 않았습니다.'},{label:'목록 아래',status:'proposal',unavailableReason:'새 목록→상세 흐름의 비교 대안으로 구현하지 않았습니다.'}],verification:'빈 목록·추가·상세 이동·프로필 없는 저장·저장된 값 출처를 브라우저에서 확인했습니다.'},
  {id:'help',title:'보조 설명 펼침',catalogId:'content-information-architecture-supplementary-disclosure',region:'환경 현황의 설정 적용 순서 아래 보조 설명',targetSelectors:['#page-body .explain'],currentVariant:'처음부터 표시',
   rationale:'처음 설정하는 사용자가 각 설정의 독립성을 바로 읽을 수 있게 하려는 설계 가설입니다.',context:'새 기기에서 설정 순서를 이해할 때',exceptions:'설치 순서·상태·오류·저장 경고는 접지 않습니다. 반복 점검 시 보조 설명만 접을 수 있습니다.',effect:'환경 현황의 보조 설명만 그대로 표시하거나 눌러 펼치게 바꿉니다. 적용 단계와 행동 버튼은 남습니다.',
   controls:[{key:'help',type:'radio',choices:[{value:'expanded',label:'처음부터 표시'},{value:'collapsed',label:'눌러서 펼치기'}]}],
   alternatives:[{label:'처음부터 표시',status:'implemented',values:{help:'expanded'}},{label:'눌러서 펼치기',status:'implemented',values:{help:'collapsed'}}],verification:'펼침·키보드·기본안 복원을 확인했습니다. 이해도와 선호는 미검증입니다.'}
 ]
};
