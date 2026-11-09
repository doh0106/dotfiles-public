'use strict';
// Only public metadata and credential references belong in these summaries.
const recordFields=new Set();
function connectionLines(connection){
 const ref=credentialOf(connection.credential),profile=profileOf(connection);
 return [connection.host+' · '+connection.method.toUpperCase()+(connection.sshUser&&connection.method==='ssh'&&sshMode(connection)==='key'?' · 사용자 '+connection.sshUser:''),
  '인증: '+(connection.method==='ssh'&&sshMode(connection)==='system'?'기존 SSH 설정 사용':ref?sources[ref.source]+' · '+(ref.item||ref.variable||ref.helper||ref.id):'참조 지정 안 함'),
  profile?'자동 적용: '+profile.path:'자동 적용할 폴더 없음',...(connection.method==='ssh'&&sshMode(connection)==='key'&&connection.publicKey?['공개키: '+connection.publicKey]:[])];
}
function profileRecords(){return draft.profiles.filter(p=>p.enabled||p.id===current()?.profile).map(p=>({id:p.id,title:p.name,lines:[
 '폴더: '+p.path,'작성자: '+(p.author||'이름 미입력')+' · '+(p.email||'이메일 미입력')+(draft.git.enabled?'':' · 작성자 지정 꺼짐'),
 '연결: '+(draft.connections.filter(c=>c.kind==='git'&&c.profile===p.id).map(c=>c.name).join(', ')||'지정 안 함'),p.enabled?'규칙 사용 중':'규칙 사용 꺼짐']}));}
function credentialRecords(connection,role){return draft.credentials.filter(ref=>secretPurpose(ref)===(role==='git'&&connection.method==='ssh'?'ssh-key':'token')&&compatible(ref.source,role,connection)||ref.id===(role==='api'?connection.api.credential:connection.credential)).map(ref=>({id:ref.id,title:ref.id,lines:[
 '공급자: '+sources[ref.source],ref.source==='bitwarden'?'보관 항목: '+(ref.item||'미입력')+' · '+({note:'Secure Note',sshkey:'SSH Key',login:'Login'})[ref.kind]:ref.source==='agent'?'기존 SSH agent 사용':ref.source==='git-helper'?'도구: '+ref.helper:'환경변수 이름: '+(ref.variable||'미입력'),
 '사용 연결: '+(draft.connections.filter(c=>c.credential===ref.id||c.api.credential===ref.id).map(c=>c.name).join(', ')||'아직 없음')]}));}
function recordChoiceField(parent,label,value,getRecords,onchange,id,noneTitle){
 const records=getRecords(),select=field(parent,label,value,[['',noneTitle],...records.map(item=>[item.id,item.title])],onchange,id);
 select.hidden=true;select.tabIndex=-1;
 const wrap=select.parentElement,card=el('div',undefined,'record-current'),summary=el('div',undefined,'record-current-summary');
 const choose=button('선택·변경',()=>openRecordPicker(label,getRecords(),select.value,noneTitle,selected=>{select.value=selected;select.dispatchEvent(new Event('change',{bubbles:true}))},choose.id));
 choose.id=id+'-picker';choose.setAttribute('aria-label',label+' 선택·변경');choose.setAttribute('aria-haspopup','dialog');wrap.querySelector('label').htmlFor=choose.id;const help=select.getAttribute('aria-describedby');if(help)choose.setAttribute('aria-describedby',help);
 card.append(summary,choose);wrap.insertBefore(card,select);
 const binding={card,summary,getRecords,getValue:()=>select.value,noneTitle,attached:false};recordFields.add(binding);refreshRecordFields();
 queueMicrotask(()=>{if(card.isConnected)binding.attached=true;else recordFields.delete(binding)});return select;
}
function refreshRecordFields(){
 for(const binding of recordFields){
  if(!binding.card.isConnected&&binding.attached){recordFields.delete(binding);continue}
  if(binding.card.isConnected)binding.attached=true;
  const selected=binding.getRecords().find(item=>item.id===binding.getValue());binding.summary.replaceChildren(el('strong',selected?.title||binding.noneTitle));
  for(const line of selected?.lines||[])binding.summary.append(el('p',line));
 }
}
function openRecordPicker(title,records,value,noneTitle,onselect,returnId){
 let dialog=$('record-picker');if(!dialog){dialog=el('dialog');dialog.id='record-picker';document.body.append(dialog)}dialog.replaceChildren();dialog.setAttribute('aria-labelledby','record-picker-title');
 const heading=el('h2',title+' 선택');heading.id='record-picker-title';const hint=el('p','핵심 설정을 확인하고 선택하세요. 실제 키·토큰 값은 표시하지 않습니다.','hint');
 const search=el('input');search.type='search';search.id='record-search';search.placeholder='이름·폴더·호스트·공급자 검색';search.setAttribute('aria-label','설정 검색');
 const list=el('fieldset',undefined,'record-options'),legend=el('legend','선택할 설정');list.append(legend);let selected=value;
 const items=[{id:'',title:noneTitle,lines:['이 항목을 지정하지 않습니다.']},...records];
 for(const item of items){const label=el('label',undefined,'record-option'),radio=el('input');radio.type='radio';radio.name='record-choice';radio.value=item.id;radio.checked=item.id===value;radio.setAttribute('aria-label',item.title);radio.onchange=()=>{selected=item.id};
  const text=el('div');text.append(el('strong',item.title));for(const line of item.lines)text.append(el('p',line));label.append(radio,text);label.dataset.search=[item.title,...item.lines].join(' ').toLowerCase();list.append(label);
 }
 const result=el('p',records.length+'개 설정 · 지정하지 않음 선택 가능','hint');result.setAttribute('aria-live','polite');search.oninput=()=>{const query=search.value.trim().toLowerCase();let count=0;for(const row of list.querySelectorAll('.record-option')){row.hidden=Boolean(query)&&!row.dataset.search.includes(query);if(!row.hidden)count++}result.textContent=count?'검색 결과 '+count+'개':'검색 결과가 없습니다.'};
 const actions=el('div',undefined,'actions');actions.append(button('취소',()=>dialog.close()),button('선택',()=>{dialog.close();onselect(selected);document.getElementById(returnId)?.focus()},'btn primary'));
 dialog.append(heading,hint,search,result,list,actions);dialog.onclose=()=>document.getElementById(returnId)?.focus();dialog.showModal();search.focus();
}
