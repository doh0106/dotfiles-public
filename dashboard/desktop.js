/* Desktop-only controls; ordinary dashboard servers keep their existing behavior. */
(async()=>{
  let info;
  try { const response=await fetch('/api/desktop');if(!response.ok)return;info=await response.json();if(!info.desktop)return; } catch{return;}
  let timer;
  const controls=document.createElement('div');controls.className='desktop-controls';
  const status=document.createElement('span');status.textContent='앱 실행 · '+info.environment;
  const stop=document.createElement('button');stop.className='btn';stop.textContent='앱 서버 종료';
  controls.append(status,stop);document.querySelector('.footer').append(controls);
  async function send(action){
    const response=await fetch('/api/desktop/'+action,{method:'POST',headers:{'X-Dotfiles-Instance':info.instance}});
    if(!response.ok)throw Error('앱 서버 연결이 끊겼습니다.');
  }
  const ping=()=>send('ping').catch(()=>{status.textContent='서버 종료됨 · 아이콘으로 다시 열기';stop.disabled=true;clearInterval(timer)});
  stop.onclick=async()=>{
    if(typeof baseline!=='undefined'&&baseline&&JSON.stringify(baseline)!==JSON.stringify(draft)&&!confirm('저장하지 않은 변경이 있습니다. 저장하지 않고 앱 서버를 종료할까요?'))return;
    try{await send('stop');clearInterval(timer);stop.disabled=true;document.body.replaceChildren();const message=document.createElement('main');message.className='desktop-ended';const title=document.createElement('h1');title.textContent='Dotfiles를 종료했습니다';const text=document.createElement('p');text.textContent='이 창을 닫아도 됩니다. 다음에는 앱 아이콘으로 다시 열어주세요.';message.append(title,text);document.body.append(message);}catch(error){status.textContent=error.message;}
  };
  await ping();timer=setInterval(ping,25000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)ping()});
})();
