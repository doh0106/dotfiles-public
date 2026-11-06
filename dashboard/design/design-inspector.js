/* Dependency-free design inspector. Works as a browser script or CommonJS module. */
(function (global, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  global.DesignInspector = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const identifier = value => typeof value === 'string' && /^[a-zA-Z][a-zA-Z0-9_-]*$/.test(value);
  function createModel(manifest) {
    if (!manifest || !Array.isArray(manifest.decisions) || !manifest.decisions.length) throw Error('A manifest with decisions is required');
    if (!manifest.defaults || typeof manifest.defaults !== 'object' || Array.isArray(manifest.defaults)) throw Error('Manifest defaults are required');
    const defaults = {...manifest.defaults};
    const allowed = new Map();
    const fields = new Map();
    for (const decision of manifest.decisions) {
      if (!identifier(decision.id) || !Array.isArray(decision.controls) || !decision.controls.length) throw Error('Each decision needs a simple id and controls');
      if (fields.has(decision.id)) throw Error('Duplicate decision id: '+decision.id);
      fields.set(decision.id, decision.controls.map(control => control.key));
      for (const control of decision.controls) {
        if (!identifier(control.key) || allowed.has(control.key)) throw Error('Duplicate or missing control key: '+control.key);
        if (!own(defaults, control.key)) throw Error('Missing default for ' + control.key);
        if (control.type !== 'checkbox' && control.type !== 'radio') throw Error('Unknown control type: '+control.type);
        if (control.type === 'radio' && (!Array.isArray(control.choices) || !control.choices.length || control.choices.some(choice=>typeof choice.value!=='string' || !choice.value) || new Set(control.choices.map(choice=>choice.value)).size !== control.choices.length)) throw Error('Invalid choices for '+control.key);
        allowed.set(control.key, control.type === 'checkbox' ? [true, false] : control.choices.map(choice => choice.value));
        if (!allowed.get(control.key).includes(defaults[control.key])) throw Error('Invalid default for ' + control.key);
      }
      if (!Array.isArray(decision.alternatives) || !decision.alternatives.length) throw Error('Missing alternatives for '+decision.id);
      for (const variant of decision.alternatives) {
        if (!['implemented','proposal'].includes(variant.status)) throw Error('Invalid alternative status for '+decision.id);
        if (variant.status === 'implemented') {
          if (!variant.values || Object.keys(variant.values).some(key=>!fields.get(decision.id).includes(key)) || fields.get(decision.id).some(key=>!own(variant.values,key) || !allowed.get(key).includes(variant.values[key]))) throw Error('Incomplete implemented values for '+decision.id);
        }
      }
    }
    if (Object.keys(defaults).some(key=>!allowed.has(key))) throw Error('Default has no control');
    for (const decision of manifest.decisions) for (const variant of decision.alternatives) {
      if (variant.requires && Object.entries(variant.requires).some(([key,value])=>!allowed.has(key) || !allowed.get(key).includes(value))) throw Error('Invalid dependency for '+decision.id);
    }
    function variantFor(decision, candidate) {
      return decision.alternatives.find(variant => variant.status==='implemented' && variant.available!==false && fields.get(decision.id).every(key=>candidate[key]===variant.values[key]) && Object.entries(variant.requires||{}).every(([key,value])=>candidate[key]===value));
    }
    function valid(candidate) { return manifest.decisions.every(decision=>variantFor(decision,candidate)); }
    if (!valid(defaults)) throw Error('Defaults must be an available implemented configuration');
    const first = manifest.decisions[0].id;
    let mode = 'single', focus = first, options = {...defaults};
    function normalize(input) {
      const value = input && typeof input === 'object' && !Array.isArray(input) ? input : {};
      const result = {...defaults};
      for (const [key, values] of allowed) {
        const candidate = value[key];
        if (values.includes(candidate)) result[key] = candidate;
      }
      // Reject unavailable alternatives and dependencies, restoring only the affected decisions.
      for (let pass=0;pass<manifest.decisions.length;pass++) {
        let changed=false;
        for (const decision of manifest.decisions) if (!variantFor(decision,result)) {
          for (const key of fields.get(decision.id)) { if (result[key]!==defaults[key]) changed=true; result[key]=defaults[key]; }
        }
        if (!changed) break;
      }
      // A default alternative may itself depend on another decision. Never return
      // an invalid state if restoring individual defaults cannot resolve a cycle.
      return valid(result) ? result : {...defaults};
    }
    function snapshot() { return {mode, focus, options:{...options}}; }
    function setMode(next) {
      if (next !== 'single' && next !== 'mix') return snapshot();
      if (mode !== next && next === 'single') {
        const selected = Object.fromEntries(fields.get(focus).map(key => [key, options[key]]));
        options = normalize({...defaults, ...selected});
      }
      mode = next;
      return snapshot();
    }
    function setFocus(next) {
      if (!fields.has(next)) return snapshot();
      if (focus !== next && mode === 'single') options = {...defaults};
      focus = next;
      return snapshot();
    }
    function setOption(key, value) {
      if (!allowed.has(key) || !allowed.get(key).includes(value)) return snapshot();
      const decision=manifest.decisions.find(d => d.controls.some(c => c.key === key));
      const candidate={...(mode==='single' && focus!==decision.id ? defaults : options),[key]:value};
      if (!valid(candidate)) return snapshot();
      options=candidate;
      focus=decision.id;
      return snapshot();
    }
    function canSet(key,value) {
      if (!allowed.has(key) || !allowed.get(key).includes(value)) return false;
      const decision=manifest.decisions.find(d=>d.controls.some(c=>c.key===key));
      return !!valid({...(mode==='single' && focus!==decision.id ? defaults : options),[key]:value});
    }
    function unavailableReason(key,value) {
      if (canSet(key,value)) return '';
      const decision=manifest.decisions.find(d=>d.controls.some(c=>c.key===key));
      if (!decision) return '알 수 없는 설정입니다.';
      const candidate={...(mode==='single' && focus!==decision.id ? defaults : options),[key]:value};
      return manifest.decisions.filter(d=>!variantFor(d,candidate)).map(d=>{
        const variant=d.alternatives.find(v=>v.values && fields.get(d.id).every(k=>v.values[k]===candidate[k]));
        const condition=variant?.requires && Object.entries(variant.requires).map(([k,v])=>{
          const owner=manifest.decisions.find(item=>fields.get(item.id).includes(k));
          const control=owner.controls.find(c=>c.key===k);
          return owner.title+': '+(control.type==='checkbox' ? (v?'켜기':'끄기') : control.choices.find(c=>c.value===v).label);
        }).join(', ');
        return d.title+' — '+(variant?.unavailableReason || variant?.dependency || (condition?'필요한 설정: '+condition:'이 조합은 아직 구현하지 않았어요.'));
      }).join(' / ');
    }
    function reset() { options = {...defaults}; return snapshot(); }
    function configure(input) { options = normalize(input); return snapshot(); }
    return {manifest, defaults:{...defaults}, normalize, snapshot, setMode, setFocus, setOption, canSet, unavailableReason, reset, configure};
  }
  function mount({root, manifest, onChange = () => {}, onFocus = () => {}, model = createModel(manifest)}) {
    if (!root) throw Error('A root element is required');
    root.classList.add('design-inspector');
    const doc = root.ownerDocument;
    const el = (tag, text, className) => { const node = doc.createElement(tag); if (text != null) node.textContent = text; if (className) node.className = className; return node; };
    const modes = el('div', null, 'explore-modes'); modes.setAttribute('role','group'); modes.setAttribute('aria-label','실험 방식');
    for (const [id, label] of [['single','하나씩 보기'],['mix','조합해 보기']]) { const button=el('button',label); button.type='button'; button.dataset.exploreMode=id; modes.append(button); }
    const description=el('p'); description.id='mode-description';
    const focusLabel=el('label','살펴볼 요소','control-label'); focusLabel.id='focus-label';
    const focusSelect=el('select'); focusSelect.id='focus-element';
    for (const decision of manifest.decisions) { const option=el('option',decision.title); option.value=decision.id; focusSelect.append(option); }
    focusLabel.append(focusSelect);
    const groups=manifest.decisions.map(decision => {
      const fieldset=el('fieldset'); fieldset.dataset.controlGroup=decision.id;
      fieldset.append(el('legend',decision.title));
      for (const control of decision.controls) {
        const choices=control.type==='checkbox' ? [{value:true,label:control.label}] : control.choices;
        for (const choice of choices) {
          const label=el('label'); const input=el('input'); input.type=control.type==='checkbox'?'checkbox':'radio'; input.name=control.key;
          if (input.type==='radio') input.value=choice.value;
          const text=el('span',choice.label),reason=el('small',null,'unavailable-reason');
          reason.id='design-reason-'+control.key+'-'+choices.indexOf(choice);
          input.setAttribute('aria-describedby',reason.id);
          text.append(reason); label.append(input,text); fieldset.append(label);
        }
      }
      fieldset.append(el('p',decision.effect));
      const expl=el('details',null,'design-explanation'); expl.dataset.designDecision=decision.id;
      expl.append(el('summary','이 설계의 이유와 다른 안'));
      const body=el('div',null,'design-explanation-body');
      const current=el('p','선택한 방식: '+decision.currentVariant); current.dataset.currentVariant=decision.id;
      body.append(el('p','적용 위치: '+decision.region),current,el('p','기본 선택의 이유: '+decision.rationale),el('p','적용 맥락: '+decision.context),el('p','예외: '+decision.exceptions),el('p','검증: '+(decision.verification||'아직 검증하지 않은 설계 가설')));
      if (decision.catalogId) { const link=el('a','카탈로그에서 보기 ↗'); link.href=manifest.catalogBase+'#'+encodeURIComponent(decision.catalogId); link.target='_blank'; link.rel='noopener'; body.append(link); }
      else body.append(el('p','이 결정은 제품 고유 설계이며 연결된 카탈로그 항목이 없습니다.'));
      const list=el('ul');
      for (const variant of decision.alternatives) {
        const item=el('li'); item.append(el('strong',variant.label+' · '+(variant.status==='implemented'&&variant.available!==false?'체험 가능':'현재 체험 불가')));
        if (variant.dependency) item.append(doc.createTextNode(' · 필요 조건: '+variant.dependency));
        if (variant.unavailableReason) item.append(doc.createTextNode(' · 현재 불가: '+variant.unavailableReason));
        list.append(item);
      }
      body.append(list); expl.append(body); fieldset.append(expl); return fieldset;
    });
    const actions=el('div',null,'experiment-actions'); const show=el('button','바뀌는 부분 보기'); show.id='show-changed'; show.type='button';
    const reset=el('button','기본 구성으로'); reset.id='reset-config'; reset.type='button'; actions.append(show,reset);
    const status=el('p','설정을 바꾸면 해당 부분으로 이동해요.'); status.id='config-status'; status.setAttribute('role','status');
    root.replaceChildren(el('h2','어떻게 살펴볼까요?'),modes,description,focusLabel,...groups,actions,status,el('p','설정 변경 시 체험 동작은 처음 상태로 돌아가요.','experiment-footnote'));
    function refresh() {
      const state=model.snapshot();
      root.querySelectorAll('[data-explore-mode]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.exploreMode===state.mode)));
      focusLabel.hidden=state.mode==='mix'; focusSelect.value=state.focus;
      description.textContent=state.mode==='single'?'선택한 요소 외에는 기본 구성으로 보여줘요.':'여러 요소를 함께 바꿔 전체 구성을 살펴보세요.';
      root.querySelectorAll('[data-control-group]').forEach(group => group.hidden=state.mode==='single'&&group.dataset.controlGroup!==state.focus);
      for (const [key,value] of Object.entries(state.options)) root.querySelectorAll('[name="'+key+'"]').forEach(input => {
        const next=input.type==='checkbox'?!value:input.value;
        input.checked=input.type==='checkbox'?value:input.value===value;
        input.disabled=!model.canSet(key,next);
        const reason=doc.getElementById(input.getAttribute('aria-describedby'));
        reason.textContent=model.unavailableReason(key,next); reason.hidden=!input.disabled;
      });
      for (const decision of manifest.decisions) {
        const active=decision.alternatives.find(variant => variant.status==='implemented' && variant.values && Object.entries(variant.values).every(([key,value]) => state.options[key]===value));
        root.querySelector('[data-current-variant="'+decision.id+'"]').textContent='선택한 방식: '+(active?.label || decision.currentVariant);
      }
      return state;
    }
    modes.addEventListener('click',event => { const button=event.target.closest('[data-explore-mode]'); if (!button || button.dataset.exploreMode===model.snapshot().mode) return; model.setMode(button.dataset.exploreMode); onChange(refresh(),null); });
    focusSelect.addEventListener('change',event => { model.setFocus(event.target.value); onChange(refresh(),model.snapshot().focus); });
    root.addEventListener('change',event => { const input=event.target; if (!input.name || !own(model.defaults,input.name)) return; model.setOption(input.name,input.type==='checkbox'?input.checked:input.value); status.textContent=manifest.decisions.find(d=>d.id===model.snapshot().focus).title+' 설정을 적용했어요. 해당 부분을 확인해 보세요.'; onChange(refresh(),model.snapshot().focus); });
    reset.addEventListener('click',() => { model.reset(); onChange(refresh(),model.snapshot().focus); status.textContent='기본 구성으로 돌아왔어요.'; });
    show.addEventListener('click',() => onFocus(model.snapshot().focus));
    refresh();
    return {model, refresh, status};
  }
  return {createModel, mount};
});
