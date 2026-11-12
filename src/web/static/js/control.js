'use strict';
(() => {
  const root = document.getElementById('crypto-control');
  const admin = root.dataset.admin === 'true';
  const $ = id => document.getElementById(id);
  const identity = /^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$/;
  const requested = new URLSearchParams(location.search).get('device_id');
  let selected = requested || '', offset = 0, inventory = null, detail = null;
  let busy = false, refreshing = false, queued = false, generation = 0, stopped = false;
  const phases = {
    PREPARED_SERVER:'Запрос сохранён; ожидается отправка PREPARE',
    PREPARE_SENT:'PREPARE доставлен брокеру; ожидается ответ устройства',
    ACTIVATION_SENT:'ACTIVATE разрешён; ожидается подтверждение',
    DEVICE_APPLIED:'Устройство сообщило о применении; ожидается подтверждение телеметрией',
    EFFECTIVE_CONFIRMED:'Криптопрофиль подтверждён новой телеметрией',
    UNKNOWN_OUTCOME:'Результат переключения не подтверждён',
    RECOVERY_REQUIRED:'Необходимо восстановление состояния'
  };
  const auditNames = {PREPARED_SERVER:'Администратор сохранил запрос',BROKER_PUBACK:'Брокер подтвердил доставку команды',DEVICE_READY:'Устройство подтвердило готовность READY',DEVICE_REPORTED_APPLIED:'Устройство сообщило о применении',EFFECTIVE_CONFIRMED:'Профиль подтверждён телеметрией',UNKNOWN_OUTCOME:'Исход операции не подтверждён',RECONCILIATION_AUTHORIZED:'Администратор открыл окно сверки'};
  function el(tag, value, cls) {
    const n = document.createElement(tag);
    if (value !== undefined) n.textContent = String(value ?? 'Нет данных');
    if (cls) n.className = cls;
    return n;
  }
  function profile(id) { return detail?.profiles?.[id]?.algorithm || inventory?.profiles?.[id]?.algorithm || id || 'Нет подтверждённого профиля'; }
  function time(value) { const d = value ? new Date(value) : null; return d && Number.isFinite(d.getTime()) ? d.toLocaleString('ru-RU') : 'Нет данных'; }
  function fields(id, rows) { const n=$(id);n.replaceChildren();for(const [k,v] of rows)n.append(el('dt',k),el('dd',v)); }
  function event(title, text) { const n=el('div',undefined,'event');n.append(el('strong',title),el('small',text));return n; }
  async function json(url, options={}) {
    const abort = new AbortController(), timer = setTimeout(()=>abort.abort(),8000);
    try {
      const r = await fetch(url,{credentials:'same-origin',cache:'no-store',...options,signal:abort.signal});
      if (!r.ok) { const error=new Error('HTTP '+r.status);error.status=r.status;throw error; }
      return await r.json();
    } finally { clearTimeout(timer); }
  }
  function validate(data, device=null) {
    if (!data || !Array.isArray(data.items) || !data.profiles || !data.components || !data.summary || typeof data.checked_at!=='string') throw new Error('Invalid snapshot');
    for (const d of data.items) {
      if (typeof d.device_id!=='string' || !identity.test(d.device_id) || !Array.isArray(d.capabilities) || typeof d.enabled!=='boolean') throw new Error('Invalid identity');
      if (d.capabilities.some(p=>typeof p!=='string' || !Object.hasOwn(data.profiles,p))) throw new Error('Invalid capabilities');
    }
    if (device) {
      if (data.items.length!==1 || data.items[0].device_id!==device) throw new Error('Identity mismatch');
      for (const key of ['transitions','commands','acks','audit']) {
        if (!Array.isArray(data[key]) || data[key].some(row=>!row || row.device_id!==device)) throw new Error('History identity mismatch');
      }
      const d=data.items[0], receipt=d.effective_evidence;
      if (d.effective_profile && (!receipt || receipt.profile!==d.effective_profile || receipt.key_epoch!==d.key_epoch || typeof receipt.event_id!=='string')) throw new Error('Receipt mismatch');
      if (d.pending && d.pending.device_id!==device) throw new Error('Transition identity mismatch');
    }
  }
  function invalidate(message='Актуальное состояние недоступно. Управление заблокировано до успешного обновления.') {
    detail=null;$('crypto-message').textContent=message;$('crypto-message').className='error';
    $('crypto-content').hidden=true;$('crypto-worker').textContent='Текущее состояние Control Worker неизвестно';
    $('crypto-history').replaceChildren();$('crypto-effective').textContent='Актуальное состояние неизвестно';
    if (admin) { $('crypto-submit').disabled=true;$('crypto-target').disabled=true;$('crypto-reconcile').hidden=true; }
  }
  function confirmed(t) { return t.phase==='EFFECTIVE_CONFIRMED' && typeof t.telemetry_event==='string' && !!t.telemetry_event && !!t.confirmed_at; }
  function phase(t) {
    if (!t) return 'Переключение не запрошено';
    if (confirmed(t)) return phases.EFFECTIVE_CONFIRMED;
    if (t.phase==='EFFECTIVE_CONFIRMED') return 'Недостаточно данных для подтверждения результата';
    if (t.expired || !t.deadline || new Date(t.deadline).getTime()<=new Date(detail.checked_at).getTime()) return phases.UNKNOWN_OUTCOME;
    return phases[t.phase] || 'Неизвестное состояние операции';
  }
  function renderHistory(data) {
    const box=$('crypto-history');box.replaceChildren();
    if (!data.transitions.length) { box.append(el('p','Переключения этого устройства ещё не зарегистрированы.'));return; }
    for (const t of data.transitions) {
      const n=el('details');n.open=t.id===data.transitions[0].id;
      n.append(el('summary',profile(t.old_profile)+' → '+profile(t.target_profile)+' · '+phase(t)));
      const meta=el('div',undefined,'crypto-history-meta');
      meta.append(event('Transition ID',t.id),event('Инициатор',t.actor),event('Запрос создан',time(t.created_at)),event('Срок операции',time(t.deadline)));
      n.append(meta,el('h3','Команды и ответы устройства'));
      const commands=data.commands.filter(c=>c.transition_id===t.id).sort((a,b)=>a.sequence-b.sequence);
      for (const c of commands) {
        n.append(event(c.phase+' · команда',c.id+' · sequence '+c.sequence+' · '+c.status+' · попыток '+c.attempts));
        for (const a of data.acks.filter(a=>a.command_id===c.id)) n.append(event('Authenticated ACK · '+a.result,time(a.received_at)+' · '+a.id));
      }
      n.append(el('h3','События аудита по времени'));
      for (const a of data.audit.filter(a=>a.transition_id===t.id).sort((a,b)=>new Date(a.at)-new Date(b.at))) n.append(event(auditNames[a.action]||a.action,time(a.at)));
      n.append(event('Подтверждающая AEAD-телеметрия',t.telemetry_event||'Подтверждающая запись отсутствует'),event('Подтверждено сервером',time(t.confirmed_at)));
      if (t.error) n.append(event('Диагностика операции',t.error));
      box.append(n);
    }
  }
  function render(data) {
    detail=data;const d=data.items[0], receipt=d.effective_evidence, worker=data.components.control;
    $('crypto-content').hidden=false;$('crypto-message').className='';
    $('crypto-message').textContent='Устройство '+selected+' · данные PostgreSQL на '+time(data.checked_at)+' · обновление каждые 3 с';
    $('crypto-state-title').textContent='Состояние устройства '+selected;
    $('crypto-device-link').href='/devices/'+encodeURIComponent(selected);
    $('crypto-worker').replaceChildren(el('strong','Control Worker'));
    const workerText={ready:'Готов к обработке команд',stale:'Heartbeat устарел — отправка недоступна',unavailable:'Недоступен',unknown:'Состояние неизвестно'};
    $('crypto-worker').append(el('p',workerText[worker?.status]||'Состояние неизвестно'),el('small','Последний heartbeat: '+time(worker?.checked_at)+' · допустимая свежесть 10 с'));
    $('crypto-effective').textContent=profile(d.effective_profile);
    $('crypto-effective-note').textContent=(receipt?'Подтверждено сервером по принятой AEAD-телеметрии.':'Для управления нужна первая подтверждённая телеметрия.')+(data.profiles[d.effective_profile]?.lab_only?' Только software lab · backend web-процесса: '+data.profiles[d.effective_profile].implementation_id:'');
    fields('crypto-receipt',[['Подтверждено',time(receipt?.accepted_at)],['Telemetry event ID',receipt?.event_id||'Нет подтверждения'],['Эпоха / sequence',receipt?receipt.key_epoch+' / '+receipt.sequence_number:'Нет данных']]);
    $('crypto-reported').textContent=d.reported_profile?profile(d.reported_profile):'Отдельный ACK о применении ещё не получен';
    const lastAck=data.acks[0];fields('crypto-ack',[['Последний ответ',lastAck?lastAck.phase+' / '+lastAck.result:'ACK отсутствует'],['Получен',time(lastAck?.received_at)]]);
    $('crypto-capabilities').replaceChildren(...d.capabilities.map(p=>el('span',profile(p),'badge-status')));
    if (!d.capabilities.length) $('crypto-capabilities').append(el('p','Нет доступных профилей управления'));
    $('crypto-enabled').textContent=d.enabled?'Устройство разрешено в реестре':'Устройство отключено в реестре';
    const age=d.telemetry_age_seconds;
    $('crypto-last-telemetry').textContent=d.telemetry?('Последняя принятая телеметрия: '+(age<1?'<1 с':Math.floor(age)+' с')+' назад. Это свежесть данных, не MQTT presence.'):'Принятой телеметрии пока нет.';
    const operation=d.pending || data.transitions[0];const op=$('crypto-operation');op.replaceChildren(el('h3',phase(operation)));
    if (operation) {
      op.append(event('Запрошенный профиль',profile(operation.target_profile)),event('Transition ID',operation.id));
      const ids=new Set(data.commands.filter(c=>c.transition_id===operation.id).map(c=>c.id));
      const acks=data.acks.filter(a=>ids.has(a.command_id));
      const steps=el('ol',undefined,'crypto-steps');
      for (const [title,seen,note] of [
        ['Запрос сохранён',true,time(operation.created_at)],
        ['Готовность READY',acks.some(a=>a.phase==='PREPARE'&&a.result==='READY'),'Authenticated PREPARE ACK'],
        ['Сообщение о применении',acks.some(a=>a.phase==='ACTIVATE'&&a.result==='DEVICE_APPLIED'),'Authenticated ACTIVATE ACK'],
        ['Подтверждение телеметрией',confirmed(operation),operation.telemetry_event||'Ожидается новая AEAD-телеметрия']]) {
        const li=el('li',title,seen?'observed':'');li.append(el('small',seen?'Есть запись · '+note:'Запись не получена'));steps.append(li);
      }
      op.append(steps);
      if (confirmed(operation)&&!acks.some(a=>a.phase==='ACTIVATE'&&a.result==='DEVICE_APPLIED')) op.append(el('p','ACK применения отсутствует, но результат подтверждён новой телеметрией.'));
    } else op.append(el('p','Выберите поддерживаемый целевой профиль и подтвердите ручной запрос.'));
    if (admin) {
      const target=$('crypto-target'),old=target.value;target.replaceChildren();
      for (const p of d.capabilities.filter(p=>p!==d.effective_profile&&data.profiles[p]?.activation_allowed!==false)) { const o=el('option',profile(p));o.value=p;target.append(o); }
      if ([...target.options].some(o=>o.value===old)) target.value=old;
      let reason='';
      if (!d.enabled) reason='Устройство отключено в реестре.';
      else if (!d.effective_profile) reason='Дождитесь подтверждённой базовой телеметрии.';
      else if (d.pending) reason='У устройства уже есть незавершённая операция. Новый запрос заблокирован.';
      else if (data.control_mode!=='MANUAL_AUTHORIZED_CONTROL') reason='Ручное управление отключено в настройках сервера.';
      else if (worker?.status!=='ready') reason='Control Worker не подтвердил готовность. Телеметрия при этом может продолжать поступать.';
      else if (!target.options.length) reason='Другого поддерживаемого профиля нет. Например, gamma поддерживает только Ascon.';
      $('crypto-blocked').textContent=reason||'Запрос потребует отдельного подтверждения. Проверки также выполняются на сервере.';
      target.disabled=busy||!!reason;$('crypto-submit').disabled=busy||!!reason;
      $('crypto-reconcile').hidden=!(d.pending&&['UNKNOWN_OUTCOME','RECOVERY_REQUIRED'].includes(d.pending.phase)&&d.pending.activated_at&&data.control_mode==='MANUAL_AUTHORIZED_CONTROL');
      $('crypto-reconcile').disabled=busy;
    }
    renderHistory(data);
  }
  async function refresh() {
    if (refreshing) { queued=true;return; }
    refreshing=true;const own=++generation;
    try {
      const data=await json('/api/monitoring?limit=100&offset='+offset);validate(data);
      if (own!==generation) return;
      inventory=data;
      if (!selected) selected=data.items[0]?.device_id||'';
      if (!selected) { invalidate('В реестре нет устройств. Требуется provisioning.');return; }
      if (!identity.test(selected)) { invalidate('Недопустимый идентификатор устройства в адресе страницы.');return; }
      const state=await json('/api/monitoring/'+encodeURIComponent(selected));validate(state,selected);
      if (own!==generation) return;
      const picker=$('crypto-device');picker.replaceChildren();
      const entries=[...data.items];if(!entries.some(d=>d.device_id===selected))entries.push(state.items[0]);
      for (const d of entries) { const o=el('option',d.device_id+(d.enabled?'':' · отключено'));o.value=d.device_id;picker.append(o); }
      picker.value=selected;picker.disabled=busy;
      $('crypto-prev').disabled=busy||offset===0;$('crypto-next').disabled=busy||offset+data.items.length>=data.summary.provisioned;
      render(state);
    } catch (_) { if(own===generation)invalidate(); }
    finally { refreshing=false;if(queued){queued=false;refresh();} }
  }
  async function refreshSelectedAfterRequest(device) {
    // Invalidate any read started before the POST; only a new snapshot may unlock controls.
    const own=++generation;
    try {
      const state=await json('/api/monitoring/'+encodeURIComponent(device));validate(state,device);
      if(own===generation && selected===device)render(state);
    } catch (_) { if(own===generation)invalidate(); }
  }
  function confirm(text) {
    return new Promise(resolve=>{const dialog=$('crypto-confirm');dialog.returnValue='cancel';$('crypto-confirm-text').textContent=text;dialog.addEventListener('close',()=>resolve(dialog.returnValue==='confirm'),{once:true});dialog.showModal();});
  }
  async function submit(reconcile=false) {
    if (busy||!detail||detail.items[0].device_id!==selected) return;
    const d=detail.items[0],device=selected,target=$('crypto-target').value,transition=d.pending?.id;
    busy=true;$('crypto-submit').disabled=true;$('crypto-device').disabled=true;$('crypto-target').disabled=true;
    $('crypto-prev').disabled=true;$('crypto-next').disabled=true;$('crypto-reconcile').disabled=true;
    try {
      if (!await confirm(reconcile?'Устройство '+device+': открыть ограниченное окно наблюдения ранее разрешённой ACTIVATE?':'Устройство '+device+': запросить '+profile(target)+' вместо '+profile(d.effective_profile)+'?')) return;
      const result=await json('/api/control/'+encodeURIComponent(device)+(reconcile?'/reconcile':'/switch'),{
        method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content},
        body:JSON.stringify(reconcile?{transition_id:transition,ttl:60}:{profile:target,ttl:120})});
      $('crypto-request-message').textContent='Запрос сохранён. Это ещё не подтверждение смены профиля. Transition ID: '+(result.transition_id||transition);
      await refreshSelectedAfterRequest(device);
    } catch (error) {
      $('crypto-request-message').textContent=error.status>=400&&error.status<500?'Сервер отклонил запрос. Проверьте права, CSRF, возможности устройства и наличие другой операции.':'Ответ на запрос не подтверждён. Обновите состояние перед повтором: запрос мог сохраниться на сервере.';
      await refreshSelectedAfterRequest(device);
    } finally { busy=false;if(detail)render(detail);$('crypto-device').disabled=!inventory; }
  }
  $('crypto-device').onchange=()=>{
    if (busy) return;selected=$('crypto-device').value;generation++;detail=null;$('crypto-content').hidden=true;
    $('crypto-request-message').textContent='';history.replaceState(null,'','/control?device_id='+encodeURIComponent(selected));refresh();
  };
  $('crypto-prev').onclick=()=>{if(!busy){offset=Math.max(0,offset-100);refresh();}};
  $('crypto-next').onclick=()=>{if(!busy){offset+=100;refresh();}};
  $('crypto-refresh').onclick=()=>refresh();
  if (admin) { $('crypto-form').onsubmit=e=>{e.preventDefault();submit();};$('crypto-reconcile').onclick=()=>submit(true); }
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){generation++;invalidate();refresh();}});
  window.addEventListener('pagehide',()=>{stopped=true;});
  async function poll(){if(stopped)return;await refresh();setTimeout(poll,3000);}
  refresh();setTimeout(poll,3000);
})();
