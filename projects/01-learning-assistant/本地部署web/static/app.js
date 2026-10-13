'use strict';
const $ = id => document.getElementById(id);
const STORE = 'local-project-assistant-v1';
let state = {user: 'web-' + crypto.randomUUID(), conversation_id: '', messages: [],selected_list:'1'};
try {
  const saved = JSON.parse(localStorage.getItem(STORE));
  if (saved && /^web-[a-zA-Z0-9_-]+$/.test(saved.user) && Array.isArray(saved.messages)) {
    state = {user: saved.user, conversation_id: typeof saved.conversation_id === 'string' ? saved.conversation_id : '',
      messages: saved.messages.filter(m => ['user', 'assistant'].includes(m.role) && typeof m.text === 'string').slice(-60),selected_list:String(saved.selected_list || '1')};
    state.messages.forEach(m => {
      if (m.state === 'loading') {m.state = 'failed'; m.error = '上次生成被中断，请重新发送问题。';}
    });
  }
} catch (_) { /* Storage unavailable: keep this session usable. */ }
let configured = false;
let busy = false;
let settingsBusy = false;
let currentTools = [];

function persist() {
  try { localStorage.setItem(STORE, JSON.stringify({...state, messages: state.messages.slice(-60)})); } catch (_) { }
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function inlineText(node, text) {
  // 仅将成对的 ** 渲染为强调，其余一律作为文本，绝不解释模型返回的 HTML。
  text.split(/(\*\*[^*]+\*\*)/g).forEach(part => {
    node.append(part.startsWith('**') && part.endsWith('**') ? el('strong', '', part.slice(2, -2)) : document.createTextNode(part));
  });
}
function renderAnswer(node, text) {
  node.replaceChildren();
  const parts = text.split('```');
  parts.forEach((part, index) => {
    if (index % 2) {
      const code = part.replace(/^[\w+-]*\n/, '');
      node.append(el('pre', '', code));
      return;
    }
    for (const line of part.split('\n')) {
      if (!line.trim()) continue;
      let row;
      if (/^#{1,6}\s/.test(line)) {
        row = el('h3'); inlineText(row, line.replace(/^#{1,6}\s+/, ''));
      } else if (/^\s*[-*]\s/.test(line)) {
        row = el('p', 'bullet'); inlineText(row, line.replace(/^\s*[-*]\s+/, ''));
      } else {
        row = el('p'); inlineText(row, line);
      }
      node.append(row);
    }
  });
}
function scrollBottom() { $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight; }
function renderMessage(message) {
  const card = el('article', 'message ' + message.role);
  const label = el('div', 'message-label');
  if (message.role === 'assistant') label.append(el('span', 'mini-mark', '✳'));
  label.append(document.createTextNode(message.role === 'user' ? '你' : '项目助手'));
  const body = el('div', 'message-body');
  const status = el('div', 'message-state');
  card.append(label, body, status);
  $('messages').append(card);
  function update() {
    if (message.role === 'user') body.textContent = message.text;
    else renderAnswer(body, message.text);
    status.replaceChildren();
    status.className = 'message-state' + (message.state === 'failed' ? ' failed' : '');
    if (message.state === 'loading') {
      status.append(el('span', 'typing'), document.createTextNode(message.text ? ' 正在生成…' : ' 正在等待助手回答…'));
    } else if (message.state === 'failed') status.textContent = message.error || '本次回答未完成，请重试。';
  }
  update();
  if (message.form) renderForm(card,message);
  return update;
}
function pendingForm() {
  return state.messages.some(m=>m.form&&!m.form.closed&&!m.form.submitted&&(!m.form.expiration_time||m.form.expiration_time*1000>Date.now()));
}
function renderForm(card,message) {
  const form=message.form;
  const panel=el('section','confirm-card');
  panel.append(el('h3','','请确认本次操作'));
  const content=el('div');renderAnswer(content,form.content||'');panel.append(content);
  const actions=el('div','confirm-actions');
  if (form.closed) actions.append(el('p','',form.action==='cancel'?'已取消':'已处理'));
  else if(form.submitted) {
    const button=el('button','button outline','查看执行结果');button.type='button';button.disabled=busy;
    button.addEventListener('click',()=>submitForm(message,null));actions.append(button);
  } else if(form.expiration_time&&form.expiration_time*1000<=Date.now()) actions.append(el('p','','确认已过期，未提交的操作不会执行。请重新提出请求。'));
  else for(const action of form.actions||[]) {
    const button=el('button','button '+(action.id==='confirm'?'primary':'outline'),action.title||action.id);button.type='button';button.disabled=busy;
    button.addEventListener('click',()=>submitForm(message,action.id));actions.append(button);
  }
  panel.append(actions);card.append(panel);
}
async function readStream(response,accept) {
  if(!response.ok){const body=await response.json();throw new Error(body.error||'请求失败。');}
  if(!response.body)throw new Error('浏览器无法读取执行结果。');
  const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';
  try {while(true){const chunk=await reader.read();buffer+=decoder.decode(chunk.value,{stream:!chunk.done});const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines)if(line.trim())accept(JSON.parse(line));if(chunk.done){if(buffer.trim())accept(JSON.parse(buffer));break;}}}
  finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
}
async function submitForm(message,action) {
  if(busy)return;
  const form=message.form;busy=true;message.state='loading';message.error='';persist();renderMessages();updateControls();
  let finished=false;
  try {
    const response=await fetch(action?'/api/form':'/api/resume',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'project-assistant'},body:JSON.stringify({form_token:form.form_token,workflow_run_id:form.workflow_run_id,conversation_id:state.conversation_id,user:state.user,action})});
    await readStream(response,value=>{
      if(value.type==='form_submitted'){form.submitted=true;form.action=value.action;persist();}
      else if(value.type==='delta'||value.type==='replace'){message.text=value.type==='replace'?value.text:message.text+value.text;}
      else if(value.type==='tool'){currentTools.push(value);message.tools=currentTools;}
      else if(value.type==='current_list'){state.selected_list=String(value.list_id||'');}
      else if(value.type==='done'){finished=true;message.state='done';form.closed=true;state.conversation_id=value.conversation_id||state.conversation_id;}
      else if(value.type==='error'){if(value.code==='form_closed')form.submitted=true;throw new Error(value.message||'执行失败');}
    });
    if(!finished)throw new Error('结果读取中断。请点击“查看执行结果”，不要重新提交相同任务。');
  } catch(error){message.state='failed';message.error=error.message||'连接失败，请重试。';}
  finally{busy=false;persist();renderMessages();renderTools();updateControls();await loadTasks();}
}
function renderMessages() {
  $('messages').replaceChildren();
  $('welcome').classList.toggle('hidden', state.messages.length > 0);
  state.messages.forEach(renderMessage);
  scrollBottom();
}
function renderTools() {
  $('tool-list').replaceChildren();
  $('tool-count').textContent = String(currentTools.length);
  $('tool-empty').classList.toggle('hidden', currentTools.length > 0);
  for (const tool of currentTools) {
    const card = el('div', 'tool-card');
    const title = el('div', 'tool-title');
    title.append(el('span', '', tool.status === 'success' ? '✓' : '!'), document.createTextNode(tool.name || '工具调用'));
    const result = tool.result;
    const count = result && typeof result === 'object' && Number.isInteger(result.count) ? result.count : null;
    card.append(title, el('p', '', tool.status === 'success' ? (count === null ? '调用成功 · 已收到工具结果' : `查询成功 · 返回 ${count} 条任务记录`) : '调用失败 · 请查看结果'));
    const details = el('details');
    details.append(el('summary', '', '查看返回数据'), el('pre', '', typeof result === 'string' ? result : JSON.stringify(result, null, 2)));
    card.append(details); $('tool-list').append(card);
  }
  const last = state.messages.filter(m => m.role === 'assistant').at(-1);
  if (!currentTools.length && last && last.state === 'done') {
    $('tool-empty').querySelector('strong').textContent = '本次回答未调用工具';
    $('tool-empty').querySelector('p').textContent = '普通知识问答可由模型直接回答；查询进度时才需要任务工具。';
  } else {
    $('tool-empty').querySelector('strong').textContent = busy ? '正在等待工具记录' : '等待一次真实查询';
    $('tool-empty').querySelector('p').textContent = '涉及项目进度时，助手会查询数据库，调用结果将显示在这里。';
  }
}
function updateControls() {
  const pending=pendingForm();
  $('send').disabled = busy || pending || !configured || !$('query').value.trim();
  $('query').disabled = busy || pending;
  $('new-chat').disabled = busy || pending;
  $('list-select').disabled = busy || pending;
  $('setup-button').disabled = busy;
  $('setup-link').disabled = busy;
  document.querySelectorAll('.starter').forEach(button => {button.disabled = busy;});
  $('compose-status').textContent = busy ? '正在通过你的 Dify 应用处理…' : pending ? '请先确认或取消上面的操作，再继续聊天。' : 'Enter 发送 · Shift + Enter 换行';
  $('setup-hint').classList.toggle('hidden', configured);
}
async function jsonRequest(path, data) {
  const options = data === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Requested-With': 'project-assistant'}, body: JSON.stringify(data)};
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '本地服务请求失败。');
  return body;
}
async function loadStatus() {
  try {
    const status = await jsonRequest('/api/status');
    configured = status.configured;
    $('connection').classList.toggle('ready', configured);
    $('connection').replaceChildren(el('i'), document.createTextNode(configured ? '应用已配置' : '等待连接应用'));
    $('setup-button').replaceChildren(document.createTextNode(configured ? '连接设置' : '连接 Dify'), el('span', '', '↗'));
  } catch (_) {
    configured = false;
    $('connection').replaceChildren(el('i'), document.createTextNode('本地服务未连接'));
  }
  updateControls();
}
async function loadTasks() {
  $('refresh-tasks').disabled = true;
  try {
    const data = await jsonRequest('/api/tasks?list_id='+encodeURIComponent(state.selected_list||''));
    if(Array.isArray(data.lists)) {
      $('list-select').replaceChildren();
      for(const list of data.lists){const option=el('option','',list.name);option.value=String(list.id);$('list-select').append(option);}
      if(!data.lists.length){const option=el('option','','暂无清单，请通过聊天创建');option.value='';$('list-select').append(option);}
      state.selected_list=data.selected_list?String(data.selected_list.id):'';$('list-select').value=state.selected_list;persist();
    }
    $('task-list').replaceChildren();
    const done = data.tasks.filter(t => t.status === 'done').length;
    $('progress-number').textContent = `${done} / ${data.tasks.length}`;
    $('progress').max = Math.max(1, data.tasks.length); $('progress').value = done;
    $('progress-note').textContent = data.tasks.length ? `已完成 ${done} 项，下一步继续向前。` : '数据库中暂无任务记录。';
    for (const task of data.tasks) {
      const item = el('li', 'task ' + (task.status === 'done' ? 'done' : 'todo'));
      const description = el('div');
      description.append(el('span', 'task-name', task.title), el('span', 'task-state', task.status_label));
      item.append(el('span', 'task-icon', task.status === 'done' ? '✓' : '·'), description);
      $('task-list').append(item);
    }
    $('task-updated').textContent = '最近读取 ' + new Date(data.queried_at).toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
    $('task-error').classList.add('hidden');
  } catch (error) {
    $('task-error').textContent = error.message || '无法读取任务。';
    $('task-error').classList.remove('hidden');
    $('task-updated').textContent = '本次读取失败，已有列表可能不是最新记录。';
  } finally { $('refresh-tasks').disabled = false; }
}
function openSetup() {
  if (busy) return;
  $('setup-error').classList.add('hidden');
  $('api-key').value = '';
  $('setup-dialog').showModal();
}
$('setup-button').addEventListener('click', openSetup);
$('setup-link').addEventListener('click', openSetup);
$('close-setup').addEventListener('click', () => { if (!settingsBusy) $('setup-dialog').close(); });
$('setup-dialog').addEventListener('cancel', event => { if (settingsBusy) event.preventDefault(); });
$('setup-dialog').addEventListener('close', () => { $('api-key').value = ''; });
$('setup-form').addEventListener('submit', async event => {
  event.preventDefault(); if (settingsBusy) return;
  settingsBusy = true; $('save-config').disabled = true; $('close-setup').disabled = true;
  $('save-config').textContent = '正在验证连接…'; $('setup-error').classList.add('hidden');
  try {
    await jsonRequest('/api/config', {api_key: $('api-key').value.trim()});
    $('api-key').value = ''; $('setup-dialog').close();
    state.conversation_id = ''; state.messages = []; currentTools = [];
    persist(); renderMessages(); renderTools();
    await loadStatus(); $('query').focus();
  } catch (error) {
    $('setup-error').textContent = error.message || '连接失败，请重试。'; $('setup-error').classList.remove('hidden');
  } finally {
    settingsBusy = false; $('save-config').disabled = false; $('close-setup').disabled = false;
    $('save-config').textContent = '验证并连接';
  }
});
$('refresh-tasks').addEventListener('click', loadTasks);
$('list-select').addEventListener('change',()=>{
  if(busy||pendingForm())return;
  const name=$('list-select').selectedOptions[0]?.textContent;
  if(!name)return;
  if(!configured){state.selected_list=$('list-select').value;loadTasks();return;}
  $('query').value='切换到清单“'+name+'”';updateControls();$('chat-form').requestSubmit();
});
$('query').addEventListener('input', updateControls);
$('query').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault(); if (!busy && configured && $('query').value.trim()) $('chat-form').requestSubmit();
  }
});
document.querySelectorAll('.starter').forEach(button => button.addEventListener('click', () => {
  $('query').value = button.dataset.query; updateControls();
  if (!configured) openSetup(); else $('query').focus();
}));
$('new-chat').addEventListener('click', () => {
  if (busy) return;
  state.conversation_id = ''; state.messages = []; state.selected_list = '1'; currentTools = [];
  persist(); renderMessages(); renderTools(); loadTasks(); $('query').focus();
});
$('chat-form').addEventListener('submit', async event => {
  event.preventDefault(); const query = $('query').value.trim();
  if (!query || busy || pendingForm()) return;
  if (!configured) { openSetup(); return; }
  busy = true; currentTools = []; $('query').value = '';
  const answer = {role: 'assistant', text: '', state: 'loading', tools: []};
  state.messages.push({role: 'user', text: query, state: 'done'}, answer);
  persist(); renderMessages(); renderTools(); updateControls();
  const card = $('messages').lastElementChild;
  let finished = false; let lastSave = 0;
  function updateAnswer() {
    renderAnswer(card.querySelector('.message-body'), answer.text);
    scrollBottom();
    if (Date.now() - lastSave > 1000) {persist(); lastSave = Date.now();}
  }
  function accept(line) {
    if (!line.trim()) return;
    const value = JSON.parse(line);
    if (value.type === 'delta' || value.type === 'replace') {
      answer.text = value.type === 'replace' ? value.text : answer.text + value.text; updateAnswer();
    } else if (value.type === 'tool') {
      currentTools.push(value); answer.tools = currentTools; renderTools();
    } else if (value.type === 'done') {
      finished = true; answer.state = 'done';
      state.conversation_id = value.conversation_id || state.conversation_id;
    } else if(value.type==='form') {
      answer.form={...value,closed:false,submitted:false};state.conversation_id=value.conversation_id||state.conversation_id;persist();
    } else if(value.type==='paused') {
      finished=true;answer.state='waiting';state.conversation_id=value.conversation_id||state.conversation_id;
    } else if(value.type==='current_list') {
      state.selected_list=String(value.list_id||'');
    } else if (value.type === 'error') {
      throw new Error(value.message || '回答生成失败。');
    }
  }
  try {
    const response = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Requested-With': 'project-assistant'}, body: JSON.stringify({query, conversation_id: state.conversation_id, user: state.user})});
    if (!response.ok) {
      const body = await response.json(); throw new Error(body.error || '请求失败，请重试。');
    }
    if (!response.body) throw new Error('当前浏览器不支持读取回答流。');
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
    try {
      while (true) {
        const chunk = await reader.read();
        buffer += decoder.decode(chunk.value, {stream: !chunk.done});
        const lines = buffer.split('\n'); buffer = lines.pop();
        for (const line of lines) accept(line);
        if (chunk.done) {if (buffer.trim()) accept(buffer); break;}
      }
    } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    if (!finished) throw new Error('回答传输中断，当前内容可能不完整，请重试。');
  } catch (error) {
    answer.state = 'failed'; answer.error = error.message || '无法连接本地服务，请检查服务是否运行。';
  } finally {
    busy = false; persist(); renderMessages(); renderTools(); updateControls();
    $('query').focus(); loadTasks();
  }
});

const previous = state.messages.filter(m => m.role === 'assistant').at(-1);
currentTools = previous && Array.isArray(previous.tools) ? previous.tools : [];
renderMessages(); renderTools(); updateControls(); loadStatus(); loadTasks();
