'use strict';
(async()=>{
 // Ordinary dashboard sessions do not mount tools or change product rendering.
 while(!snapshot){await new Promise(resolve=>setTimeout(resolve,80));}
 if(!snapshot.design_preview)return;
 document.body.classList.add('design-preview');
 const manifest=window.DashboardDesignManifest;
 manifest.catalogBase=snapshot.design_catalog_url;
 const banner=el('div',undefined,'design-banner');
 banner.append(el('strong','설계 미리보기 · 예시 설정'));
 banner.append(el('span','저장·인증 실행은 차단됩니다. 비교 선택은 선호나 영구 채택으로 저장되지 않습니다.'));
 const toggle=button('UI 설계 살펴보기',()=>setOpen(panel.hidden));toggle.id='design-toggle';toggle.setAttribute('aria-controls','design-panel');
 banner.append(toggle);document.body.prepend(banner);
 const panel=el('aside',undefined,'design-panel');panel.id='design-panel';panel.setAttribute('aria-label','UI 설계 검사 도구');
 const panelHead=el('div',undefined,'design-panel-head');panelHead.append(el('strong','UI 설계 살펴보기'));
 const close=button('닫기',()=>{setOpen(false);toggle.focus()});close.setAttribute('aria-label','설계 검사 도구 닫기');panelHead.append(close);panel.append(panelHead);
 const tools=el('div');panel.append(tools);document.body.append(panel);
 function setOpen(open){panel.hidden=!open;document.body.classList.toggle('design-panel-open',open);toggle.setAttribute('aria-expanded',String(open));if(open)close.focus();}
 panel.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();setOpen(false);toggle.focus()}});
 let options={...manifest.defaults};
 function apply(next){options={...next};document.body.dataset.designNavigation=options.navigation;document.body.dataset.designDetail=options.detail;syncProduct();}
 function syncProduct(){
  document.body.dataset.designView=view;
  if(view!=='overview')return;
  if(options.help==='collapsed'){
   for(const note of all('#page-body .explain')){
    if(note.parentElement.classList.contains('design-help'))continue;
    const details=el('details',undefined,'design-help'),summary=el('summary');summary.textContent='보조 설명: '+(note.querySelector('strong')?.textContent||'자세히 보기');
    note.before(details);details.append(summary,note);
   }
  }else for(const details of all('#page-body .design-help')){const note=details.querySelector('.explain');details.replaceWith(note);}
 }
 const baseNavigate=navigate;
 navigate=function(next){baseNavigate(next);syncProduct()};
 const observer=new MutationObserver(()=>syncProduct());observer.observe($('page-body'),{childList:true,subtree:true});
 function reveal(id){
  const destination={detail:'connections',help:'overview'}[id];if(destination&&view!==destination)navigate(destination);
  let target=id==='navigation'?(window.innerWidth<=720?$('mobile-nav'):document.querySelector('.sidebar')):id==='detail'?document.querySelector('#page-body .inspector'):document.querySelector('#page-body .design-help, #page-body .explain');
  if(!target)return;
  all('.design-highlight').forEach(node=>node.classList.remove('design-highlight'));target.classList.add('design-highlight');
  target.scrollIntoView({block:'nearest',behavior:'instant'});
 }
 const inspector=DesignInspector.mount({root:tools,manifest,onChange(state,target){apply(state.options);if(target)reveal(target)},onFocus:reveal});
 // This footnote describes the product adapter accurately: no product input is reset.
 tools.querySelector('.experiment-footnote').textContent='비교는 배치·표시만 바꿉니다. 편집 초안은 유지하고, 비교용 펼침 상태는 기본 구성으로 돌아가면 초기화합니다.';
 window.dashboardDesign={inspector,apply,reveal};
 apply(inspector.model.snapshot().options);setOpen(true);
 // Save remains visibly unavailable as well as server-enforced; preview compilation is allowed.
 $('confirm-review').disabled=true;$('confirm-review').textContent='미리보기 · 저장 불가';
})();
