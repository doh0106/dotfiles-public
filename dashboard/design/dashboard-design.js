/* UI catalog mappings are design hypotheses, not confirmed user preferences. */
window.DashboardDesignManifest={
 id:'dotfiles-environment-dashboard',product:'dotfiles · 개인 환경 대시보드',
 recordType:'unverified-design-hypothesis',catalogBase:null,
 verification:'구현 동작을 별도로 확인합니다. 사용자 선호·찾기 성능은 미검증입니다.',
 defaults:{navigation:'sidebar',detail:'beside',help:'expanded'},
 decisions:[
  {id:'navigation',title:'주 메뉴 위치',catalogId:'navigation-findability-primary-navigation-placement',region:'호스트 설정·Git/SSH·서비스·개발 환경 메뉴',targetSelectors:['.sidebar'],currentVariant:'왼쪽 메뉴',
   rationale:'설정 범위를 묶어 보여주고 화면을 오가며 현재 위치를 유지하려는 설계 가설입니다.',context:'데스크톱에서 여러 환경 설정을 점검할 때',exceptions:'좁은 화면에서는 두 안 모두 기존 화면 선택 메뉴를 사용합니다. 상단 안은 줄바꿈으로 목적지를 유지합니다.',effect:'실제 메뉴 전체를 왼쪽 또는 페이지 상단에 배치합니다. 목적지와 메뉴 이름은 유지합니다.',
   controls:[{key:'navigation',type:'radio',choices:[{value:'sidebar',label:'왼쪽 메뉴'},{value:'top',label:'상단 메뉴'}]}],
   alternatives:[{label:'왼쪽 메뉴',status:'implemented',values:{navigation:'sidebar'}},{label:'상단 메뉴',status:'implemented',values:{navigation:'top'}},{label:'자주 쓰는 메뉴만 자동 노출',status:'proposal',unavailableReason:'사용 빈도 기록·정렬·숨긴 목적지 접근 규칙을 구현하지 않았습니다.'}],verification:'메뉴 이동·모바일 선택·키보드 접근을 확인했습니다. 두 배치의 탐색 성능은 비교하지 않았습니다.'},
  {id:'detail',title:'Git 연결 상세 위치',catalogId:'spatial-adaptive-layout-list-detail',region:'Git · SSH 연결의 목록과 선택한 연결 편집 영역',targetSelectors:['#page-body .inspector'],currentVariant:'목록 오른쪽',
   rationale:'목록의 선택 항목을 보면서 접속·인증 설정을 편집하려는 설계 가설입니다.',context:'GitHub·GitLab·서버 접속 설정을 하나씩 확인할 때',exceptions:'좁은 화면에서는 두 안 모두 목록 아래에 배치합니다. 설정 항목과 입력 초안은 유지합니다.',effect:'같은 상세 편집 영역을 목록 옆 또는 목록 아래로 옮깁니다. 선택 항목과 작성 중 입력은 바꾸지 않습니다.',
   controls:[{key:'detail',type:'radio',choices:[{value:'beside',label:'목록 오른쪽'},{value:'below',label:'목록 아래'}]}],
   alternatives:[{label:'목록 오른쪽',status:'implemented',values:{detail:'beside'}},{label:'목록 아래',status:'implemented',values:{detail:'below'}},{label:'별도 상세 화면',status:'proposal',unavailableReason:'뒤로 이동과 편집 초안 복원 경로가 없습니다.'}],verification:'동일 DOM·선택·입력 유지와 좁은 화면을 확인했습니다. 사용자 편집 효율은 미검증입니다.'},
  {id:'help',title:'보조 설명 펼침',catalogId:'content-information-architecture-supplementary-disclosure',region:'환경 개요의 설정 적용 순서 아래 보조 설명',targetSelectors:['#page-body .explain'],currentVariant:'처음부터 표시',
   rationale:'처음 설정하는 사용자가 각 설정의 독립성을 바로 읽을 수 있게 하려는 설계 가설입니다.',context:'새 기기에서 설정 순서를 이해할 때',exceptions:'설치 순서·상태·오류·저장 경고는 접지 않습니다. 반복 점검 시 보조 설명만 접을 수 있습니다.',effect:'환경 개요의 보조 설명만 그대로 표시하거나 눌러 펼치게 바꿉니다. 적용 단계와 행동 버튼은 남습니다.',
   controls:[{key:'help',type:'radio',choices:[{value:'expanded',label:'처음부터 표시'},{value:'collapsed',label:'눌러서 펼치기'}]}],
   alternatives:[{label:'처음부터 표시',status:'implemented',values:{help:'expanded'}},{label:'눌러서 펼치기',status:'implemented',values:{help:'collapsed'}}],verification:'펼침·키보드·기본안 복원을 확인했습니다. 이해도와 선호는 미검증입니다.'}
 ]
};
