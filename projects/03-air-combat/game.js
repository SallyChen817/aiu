/* Canvas arcade game. All assets are drawn locally; no network dependencies. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id), C=GameCore;
 const canvas=$('game'), ctx=canvas.getContext('2d'), W=600,H=800;
 const STORE='thunder-squadron-v1', skins={cyan:'#67e8f9',violet:'#b99cff',amber:'#ffd480'};
 let save,owned=['cyan'],skin='cyan',storageOK=true;
 try {const data=JSON.parse(localStorage.getItem(STORE)||'{}');save=C.cleanSave(data);owned=['cyan',...(Array.isArray(data.owned)?data.owned.filter(x=>x in skins):[])];if(owned.includes(data.skin))skin=data.skin;} catch {save=C.cleanSave(null);storageOK=false;}
 function persist(){try{localStorage.setItem(STORE,JSON.stringify({...save,owned,skin}));}catch{storageOK=false;}updateSave();}
 function updateSave(){$('best').textContent=save.best.toLocaleString();$('coins').textContent=save.coins.toLocaleString();$('storage-note').textContent=storageOK?'战绩保存在当前浏览器':'存储不可用，战绩仅在本次页面保留';}
 let state='menu',g=null,last=0,bgTime=0,shake=0,toastUntil=0,keys=new Set(),pointer=null,sound=false,audioCtx=null,reviewAbort=null;
 const stars=Array.from({length:100},()=>({x:Math.random()*W,y:Math.random()*H,z:.3+Math.random()*1.3}));
 const rand=(a,b)=>a+Math.random()*(b-a),clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
 const clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
 function beep(freq=440,duration=.06,type='sine',volume=.035){
  if(!sound)return;try{audioCtx??=new (window.AudioContext||window.webkitAudioContext)();if(audioCtx.state==='suspended')audioCtx.resume();const o=audioCtx.createOscillator(),v=audioCtx.createGain();o.type=type;o.frequency.setValueAtTime(freq,audioCtx.currentTime);o.frequency.exponentialRampToValueAtTime(Math.max(30,freq/3),audioCtx.currentTime+duration);v.gain.setValueAtTime(volume,audioCtx.currentTime);v.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+duration);o.connect(v);v.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+duration);}catch{sound=false;}
 }
 function toast(text){$('toast').textContent=text;$('toast').classList.add('show');toastUntil=bgTime+2.3;}
 function show(id,on){$(id).classList.toggle('hidden',!on);}
 function clearReview(){reviewAbort?.abort();reviewAbort=null;$('ai-review').disabled=false;$('ai-review').textContent='请本地 AI 教官点评 ↗';}
 function start(){
  clearReview();keys.clear();pointer=null;
  g={t:0,score:0,kills:0,combo:0,maxCombo:0,comboTimer:0,hp:3,missiles:5,level:1,invuln:2,fire:0,spawn:.7,drop:7,missileCooldown:0,shots:0,hits:0,damage:0,usedMissiles:0,sector:1,bossSpawned:false,bossKilled:false,settled:false,player:{x:W/2,y:H-120,r:14},bullets:[],enemies:[],hostile:[],rockets:[],particles:[],drops:[],labels:[]};
  state='playing';['menu','paused','result','boss-hud'].forEach(x=>show(x,false));$('pause').disabled=false;$('pause').textContent='暂停 P';$('status').textContent='作战中';canvas.focus();toast('SECTOR 01 · 突破近地轨道');beep(550,.2);hud();
 }
 function pause(){if(state==='playing'){state='paused';keys.clear();pointer=null;show('paused',true);$('pause').textContent='继续 P';$('status').textContent='已暂停';}else if(state==='paused'){state='playing';show('paused',false);$('pause').textContent='暂停 P';$('status').textContent='作战中';canvas.focus();}}
 function burst(x,y,color,n=18,force=1){for(let i=0;i<n;i++){const a=Math.random()*Math.PI*2,s=rand(30,230)*force;g.particles.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life:rand(.25,.7),max:.7,color,r:rand(1,4)});}}
 function label(x,y,text,color='#67e8f9'){g.labels.push({x,y,text,color,life:1});}
 function fireMissile(){
  if(state!=='playing'||g.missileCooldown>0)return;if(g.missiles<=0){toast('导弹耗尽 · 收集 M 补给');return;}
  g.missiles--;g.usedMissiles++;g.missileCooldown=.45;
  for(const dx of [-13,13])g.rockets.push({x:g.player.x+dx,y:g.player.y-12,vx:dx*4,vy:-350,r:8,life:5,trail:[]});
  beep(240,.25,'sawtooth',.035);hud();
 }
 function addEnemy(type){
  const info={scout:{hp:2,r:19,speed:95,color:'#ff8caa'},swift:{hp:2,r:16,speed:165,color:'#f9bd77'},heavy:{hp:8,r:29,speed:63,color:'#b79aff'}}[type];
  g.enemies.push({...info,type,x:rand(45,W-45),y:-45,age:0,shoot:rand(1.5,3),phase:Math.random()*6,hpMax:info.hp});
 }
 function addBoss(){g.bossSpawned=true;g.enemies.push({type:'boss',x:W/2,y:-100,r:72,hp:230,hpMax:230,age:0,shoot:1,color:'#ff6d9e'});show('boss-hud',true);toast('警报 · 虚空旗舰接近');beep(120,.6,'sawtooth',.055);}
 function damagePlayer(){if(g.invuln>0)return;g.hp--;g.damage++;g.combo=0;g.comboTimer=0;g.invuln=2;g.level=Math.max(1,g.level-1);shake=12;burst(g.player.x,g.player.y,'#67e8f9',25);beep(80,.3,'sawtooth',.06);if(g.hp<=0)finish(false);}
 function killEnemy(e){
  if(e.dead)return;e.dead=true;g.kills++;g.combo++;g.maxCombo=Math.max(g.maxCombo,g.combo);g.comboTimer=4;
  const score=C.points(e.type,g.combo);g.score+=score;label(e.x,e.y,`+${score}`);burst(e.x,e.y,e.color,e.type==='boss'?100:25,e.type==='boss'?2:1);shake=e.type==='boss'?20:3;beep(e.type==='boss'?65:110,.15,'triangle',.05);
  if(e.type==='boss'){g.bossKilled=true;finish(true);return;}
  if(Math.random()<.16)g.drops.push({x:e.x,y:e.y,r:17,type:['W','M','+'][Math.floor(Math.random()*3)]});
 }
 function finish(win){
  if(g.settled)return;g.settled=true;state='result';keys.clear();pointer=null;
  if(win)g.score+=g.hp*500;
  const record=g.score>save.best;save=C.settle(save,g.score);persist();
  $('pause').disabled=true;$('status').textContent=win?'任务完成':'任务结束';show('boss-hud',false);show('result',true);
  $('result-label').textContent=win?'MISSION COMPLETE':'MISSION ENDED';$('result-title').textContent=win?'空域已肃清':'整备，再出击';$('result-score').textContent=g.score.toLocaleString();
  $('result-record').textContent=`${record?'新纪录！ · ':''}获得 ${Math.floor(g.score/100)} 星币${win?` · 余命奖励 ${g.hp*500}`:''}`;
  $('result-stats').innerHTML=`<div><b>${g.kills}</b>击落敌机</div><div><b>${clock(g.t)}</b>飞行时间</div><div><b>${g.maxCombo}</b>最高连击</div>`;
  $('review-source').textContent='本地规则分析';$('review').textContent=`${win?'成功击败旗舰。':'本次突破了第 '+g.sector+' 空域。'}${g.damage>=3?'保持横向移动，避免停在敌机正下方。':'你保持了不错的生存能力。'}${g.usedMissiles===0?'记得用空格发射导弹，重型敌机和旗舰是合适目标。':`本局使用 ${g.usedMissiles} 次导弹，拾取紫色 M 补给可继续补充。`} 连击窗口为 4 秒，持续击落敌机能提高得分倍率。`;
  hud();
 }
 function hud(){if(!g)return;$('score').textContent=String(g.score).padStart(6,'0');$('kills').textContent=g.kills;$('time').textContent=clock(g.t);$('health').textContent='♥ '.repeat(Math.max(0,g.hp))+'♡ '.repeat(3-Math.max(0,g.hp));$('weapon').textContent=`武器 LV.${g.level}`;$('missile').innerHTML=`导弹 × ${g.missiles} <kbd>SPACE</kbd>`;$('combo').textContent=g.combo>1?`${g.combo} COMBO · ×${C.multiplier(g.combo)}`:'锁定 · 自动开火';$('wave').textContent=`0${g.sector} / 03 空域`;$('sector').textContent=`SECTOR 0${g.sector} · ${['近地轨道','陨星走廊','旗舰领域'][g.sector-1]}`;const boss=g.enemies.find(e=>e.type==='boss'&&!e.dead);if(boss){$('boss-bar').style.width=`${Math.max(0,boss.hp/boss.hpMax*100)}%`;$('boss-percent').textContent=`${Math.ceil(Math.max(0,boss.hp/boss.hpMax*100))}%`;}}
 function update(dt){
  g.t+=dt;g.invuln=Math.max(0,g.invuln-dt);g.missileCooldown-=dt;g.comboTimer-=dt;if(g.comboTimer<=0)g.combo=0;
  const stage=Math.min(3,1+Math.floor(g.t/30));if(stage!==g.sector){g.sector=stage;toast(`SECTOR 0${stage} · ${stage===2?'穿越陨星走廊':'进入旗舰领域'}`);}
  let dx=(keys.has('ArrowRight')||keys.has('d')?1:0)-(keys.has('ArrowLeft')||keys.has('a')?1:0),dy=(keys.has('ArrowDown')||keys.has('s')?1:0)-(keys.has('ArrowUp')||keys.has('w')?1:0);
  if(dx||dy){const length=Math.hypot(dx,dy);g.player.x+=dx/length*350*dt;g.player.y+=dy/length*350*dt;pointer=null;}else if(pointer){const k=1-Math.exp(-15*dt);g.player.x+=(pointer.x-g.player.x)*k;g.player.y+=(pointer.y-g.player.y)*k;}
  g.player.x=clamp(g.player.x,23,W-23);g.player.y=clamp(g.player.y,95,H-65);
  if(keys.has(' '))fireMissile();
  g.fire-=dt;if(g.fire<=0){g.fire=.14;const angles=g.level===1?[0]:g.level===2?[-.045,.045]:g.level===3?[-.14,0,.14]:[-.23,-.115,0,.115,.23];for(const a of angles){g.bullets.push({x:g.player.x+Math.sin(a)*40,y:g.player.y-24,vx:Math.sin(a)*650,vy:-Math.cos(a)*650,r:5});g.shots++;}beep(850,.025,'sine',.009);}
  if(g.t>=85&&!g.bossSpawned)addBoss();
  g.spawn-=dt;if(g.spawn<=0){g.spawn=g.bossSpawned?3.3:Math.max(.38,1.05-g.t*.006);const r=Math.random();addEnemy(r<.5?'scout':r<.8?'swift':'heavy');}
  g.drop-=dt;if(g.drop<=0){g.drop=11;g.drops.push({x:rand(50,W-50),y:-20,r:17,type:g.level<3?'W':Math.random()<.5?'M':'+'});}
  for(const e of g.enemies){
   e.age+=dt;e.shoot-=dt;
   if(e.type==='boss'){e.y=Math.min(135,e.y+65*dt);e.x=W/2+Math.sin(e.age*.65)*160;if(e.y>=120&&e.shoot<=0){e.shoot=e.hp<100?.68:1.05;const aimed=Math.atan2(g.player.y-e.y,g.player.x-e.x);for(let i=-2;i<=2;i++){const a=aimed+i*.24;g.hostile.push({x:e.x,y:e.y+30,vx:Math.cos(a)*180,vy:Math.sin(a)*180,r:7});}if(e.hp<100)for(let i=0;i<10;i++){const a=i*Math.PI/5+e.age;g.hostile.push({x:e.x,y:e.y,vx:Math.cos(a)*115,vy:Math.sin(a)*115,r:5});}}}
   else {e.y+=e.speed*dt*(1+(g.sector-1)*.12);e.x=clamp(e.x+Math.sin(e.age*2+e.phase)*(e.type==='swift'?95:24)*dt,20,W-20);if(e.shoot<=0&&e.y>20){e.shoot=e.type==='heavy'?1.8:3;const a=Math.atan2(g.player.y-e.y,g.player.x-e.x);g.hostile.push({x:e.x,y:e.y+e.r,vx:Math.cos(a)*145,vy:Math.sin(a)*145,r:5});}}
   if(e.y>H+60)e.dead=true;
  }
  for(const b of g.bullets){b.x+=b.vx*dt;b.y+=b.vy*dt;for(const e of g.enemies){if(!b.dead&&!e.dead&&C.hit(b,e)){b.dead=true;g.hits++;e.hp--;burst(b.x,b.y,'#a9fbff',3,.3);if(e.hp<=0)killEnemy(e);}}if(state!=='playing')return;}
  for(const m of g.rockets){m.life-=dt;const target=g.enemies.filter(e=>!e.dead&&e.y>0).sort((a,b)=>(a.x-m.x)**2+(a.y-m.y)**2-((b.x-m.x)**2+(b.y-m.y)**2))[0];if(target){const a=Math.atan2(target.y-m.y,target.x-m.x),k=1-Math.exp(-5*dt);m.vx+=(Math.cos(a)*430-m.vx)*k;m.vy+=(Math.sin(a)*430-m.vy)*k;}m.x+=m.vx*dt;m.y+=m.vy*dt;m.trail.push({x:m.x,y:m.y});if(m.trail.length>12)m.trail.shift();if(target&&C.hit(m,target)){m.dead=true;target.hp-=12;burst(m.x,m.y,'#c4a7ff',28);shake=6;if(target.hp<=0)killEnemy(target);}if(state!=='playing')return;}
  for(const b of g.hostile){b.x+=b.vx*dt;b.y+=b.vy*dt;if(C.hit(b,g.player)){b.dead=true;damagePlayer();if(state!=='playing')return;}}
  for(const e of g.enemies){if(!e.dead&&C.hit(e,g.player)){damagePlayer();if(e.type!=='boss'){e.dead=true;burst(e.x,e.y,e.color);}if(state!=='playing')return;}}
  for(const d of g.drops){d.y+=100*dt;if(C.hit({...d,r:27},g.player)){d.dead=true;if(d.type==='W'){g.level=Math.min(4,g.level+1);toast(`火力提升 · LV.${g.level}`);}else if(d.type==='M'){g.missiles=Math.min(20,g.missiles+3);toast('导弹补充 +3');}else {g.hp=Math.min(3,g.hp+1);g.invuln=3;toast('装甲修复 · 护盾启动');}beep(660,.2,'sine');}}
  g.bullets=g.bullets.filter(b=>!b.dead&&b.y>-30&&b.x>-20&&b.x<W+20);g.enemies=g.enemies.filter(e=>!e.dead);g.hostile=g.hostile.filter(b=>!b.dead&&b.y<H+20&&b.y>-100&&b.x>-30&&b.x<W+30);g.rockets=g.rockets.filter(m=>!m.dead&&m.life>0);g.drops=g.drops.filter(d=>!d.dead&&d.y<H+30);
  hud();
 }
 function ship(c,x,y,size,color,kind='player',angle=0){
  c.save();c.translate(x,y);c.rotate(angle);c.scale(size,size);
  const enemy=kind!=='player';if(enemy)c.rotate(Math.PI);
  c.shadowBlur=12;c.shadowColor=color;
  c.fillStyle=color+'40';c.beginPath();c.moveTo(-11,23);c.lineTo(-7,40+Math.sin(bgTime*24)*7);c.lineTo(-3,23);c.fill();c.beginPath();c.moveTo(3,23);c.lineTo(7,40+Math.cos(bgTime*24)*7);c.lineTo(11,23);c.fill();
  c.shadowBlur=0;c.fillStyle=enemy?'#503751':'#253f58';c.strokeStyle=color;c.lineWidth=1.3;
  c.beginPath();c.moveTo(0,-31);c.lineTo(9,-9);c.lineTo(29,16);c.lineTo(28,23);c.lineTo(11,17);c.lineTo(9,29);c.lineTo(0,22);c.lineTo(-9,29);c.lineTo(-11,17);c.lineTo(-28,23);c.lineTo(-29,16);c.lineTo(-9,-9);c.closePath();c.fill();c.stroke();
  c.fillStyle=enemy?'#b1809f':'#91b6cc';c.beginPath();c.moveTo(0,-27);c.lineTo(7,14);c.lineTo(0,21);c.lineTo(-7,14);c.closePath();c.fill();
  c.fillStyle=color;c.shadowBlur=15;c.shadowColor=color;c.beginPath();c.moveTo(0,-14);c.lineTo(4,1);c.lineTo(0,7);c.lineTo(-4,1);c.closePath();c.fill();c.fillRect(-21,13,8,2);c.fillRect(13,13,8,2);c.restore();
 }
 function drawBoss(e){ctx.save();ctx.translate(e.x,e.y);ctx.fillStyle='#362841';ctx.strokeStyle='#ff6d9e';ctx.lineWidth=2;ctx.shadowBlur=18;ctx.shadowColor='#a92d6655';ctx.beginPath();ctx.moveTo(-85,-20);ctx.lineTo(-50,-44);ctx.lineTo(-18,-21);ctx.lineTo(0,-40);ctx.lineTo(18,-21);ctx.lineTo(50,-44);ctx.lineTo(85,-20);ctx.lineTo(71,30);ctx.lineTo(32,15);ctx.lineTo(15,48);ctx.lineTo(-15,48);ctx.lineTo(-32,15);ctx.lineTo(-71,30);ctx.closePath();ctx.fill();ctx.stroke();ctx.fillStyle='#ff8bb0';ctx.fillRect(-58,5,23,5);ctx.fillRect(35,5,23,5);ctx.beginPath();ctx.arc(0,0,15+Math.sin(bgTime*5)*2,0,Math.PI*2);ctx.fill();ctx.fillStyle='#fff';ctx.fillRect(-3,-10,6,20);ctx.restore();}
 function background(dt){
  ctx.fillStyle='#070e1d';ctx.fillRect(0,0,W,H);
  const neb=ctx.createRadialGradient(W*.7,H*.3,0,W*.7,H*.3,420);neb.addColorStop(0,'#25215455');neb.addColorStop(.5,'#122c4935');neb.addColorStop(1,'#070e1d00');ctx.fillStyle=neb;ctx.fillRect(0,0,W,H);
  ctx.strokeStyle='#38658b13';ctx.lineWidth=1;for(let x=-W;x<W*2;x+=80){ctx.beginPath();ctx.moveTo(W/2+(x-W/2)*.2,0);ctx.lineTo(x,H);ctx.stroke();}for(let y=0;y<H;y+=80){const yy=(y+bgTime*20)%H;ctx.beginPath();ctx.moveTo(0,yy);ctx.lineTo(W,yy);ctx.stroke();}
  for(const s of stars){if(state!=='paused')s.y=(s.y+dt*s.z*(state==='playing'?65:18))%H;ctx.fillStyle=`rgba(179,209,255,${s.z*.42})`;ctx.fillRect(s.x,s.y,s.z, state==='playing'?s.z*3:s.z);}
  ctx.save();ctx.translate(520,150);ctx.rotate(-.45);ctx.strokeStyle='#8d7ba818';ctx.lineWidth=1;ctx.beginPath();ctx.ellipse(0,0,140,34,0,0,Math.PI*2);ctx.stroke();const planet=ctx.createRadialGradient(-20,-20,5,0,0,65);planet.addColorStop(0,'#3b4964');planet.addColorStop(1,'#0e192c');ctx.fillStyle=planet;ctx.beginPath();ctx.arc(0,0,65,0,Math.PI*2);ctx.fill();ctx.restore();
 }
 function draw(dt){
  background(dt);if(!g||state==='menu'){ship(ctx,W/2,H*.72,1.7,skins[skin]);return;}
  ctx.save();if(shake>0){ctx.translate(rand(-shake,shake),rand(-shake,shake));shake=Math.max(0,shake-dt*40);}
  for(const d of g.drops){const color=d.type==='W'?'#67e8f9':d.type==='M'?'#b99cff':'#74edb6';ctx.save();ctx.translate(d.x,d.y);ctx.shadowColor=color;ctx.shadowBlur=13;ctx.fillStyle='#122233';ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.roundRect(-15,-15,30,30,6);ctx.fill();ctx.stroke();ctx.fillStyle=color;ctx.font='bold 17px Consolas';ctx.textAlign='center';ctx.fillText(d.type,0,6);ctx.restore();}
  ctx.shadowBlur=13;ctx.shadowColor=skins[skin];ctx.fillStyle=skins[skin];for(const b of g.bullets){ctx.fillRect(b.x-2,b.y-9,4,18);}ctx.shadowBlur=0;
  for(const m of g.rockets){ctx.strokeStyle='#b99cff88';ctx.lineWidth=3;ctx.beginPath();m.trail.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();ctx.save();ctx.translate(m.x,m.y);ctx.rotate(Math.atan2(m.vy,m.vx)+Math.PI/2);ctx.fillStyle='#ebe1ff';ctx.fillRect(-3,-9,6,17);ctx.fillStyle='#b99cff';ctx.fillRect(-2,8,4,9);ctx.restore();}
  for(const e of g.enemies){if(e.dead)continue;if(e.type==='boss')drawBoss(e);else ship(ctx,e.x,e.y,e.type==='heavy'?1.2:e.type==='swift'?.65:.8,e.color,e.type);if(e.hp<e.hpMax&&e.type!=='boss'){ctx.fillStyle='#3a293f';ctx.fillRect(e.x-20,e.y-e.r-12,40,3);ctx.fillStyle=e.color;ctx.fillRect(e.x-20,e.y-e.r-12,40*e.hp/e.hpMax,3);}}
  ctx.shadowBlur=10;ctx.shadowColor='#ff6688';for(const b of g.hostile){ctx.fillStyle='#ff88a3';ctx.beginPath();ctx.arc(b.x,b.y,b.r,0,Math.PI*2);ctx.fill();ctx.fillStyle='#ffdfdb';ctx.beginPath();ctx.arc(b.x,b.y,b.r*.4,0,Math.PI*2);ctx.fill();}ctx.shadowBlur=0;
  if(g.hp>0&&(g.invuln<=0||Math.floor(bgTime*13)%2===0))ship(ctx,g.player.x,g.player.y,.9,skins[skin]);
  if(g.invuln>0&&g.hp>0){ctx.strokeStyle=skins[skin]+'88';ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(g.player.x,g.player.y,38,0,Math.PI*2);ctx.stroke();}
  for(const p of g.particles){if(state!=='paused'){p.life-=dt;p.x+=p.vx*dt;p.y+=p.vy*dt;}ctx.globalAlpha=Math.max(0,p.life/p.max);ctx.fillStyle=p.color;ctx.fillRect(p.x,p.y,p.r,p.r);}ctx.globalAlpha=1;g.particles=g.particles.filter(p=>p.life>0);
  for(const l of g.labels){if(state!=='paused'){l.life-=dt;l.y-=35*dt;}ctx.globalAlpha=Math.max(0,l.life);ctx.fillStyle=l.color;ctx.font='bold 15px Consolas';ctx.textAlign='center';ctx.fillText(l.text,l.x,l.y);}ctx.globalAlpha=1;g.labels=g.labels.filter(l=>l.life>0);ctx.restore();
 }
 function preview(){const p=$('ship-preview'),c=p.getContext('2d');c.clearRect(0,0,280,190);c.strokeStyle='#314259';c.lineWidth=.5;for(const r of [45,70]){c.beginPath();c.ellipse(140,100,r,r*.55,0,0,Math.PI*2);c.stroke();}c.strokeStyle='#274359';c.beginPath();c.moveTo(30,100);c.lineTo(250,100);c.moveTo(140,25);c.lineTo(140,175);c.stroke();ship(c,140,95,1.8,skins[skin], 'player',-.2);}
 function refreshSkin(){document.querySelectorAll('[data-skin]').forEach(b=>b.classList.toggle('selected',b.dataset.skin===skin));$('skin-label').textContent=({cyan:'极光蓝',violet:'脉冲紫',amber:'日冕金'}[skin])+' · 已装备';preview();}
 document.querySelectorAll('[data-skin]').forEach(b=>b.addEventListener('click',()=>{const selected=b.dataset.skin,cost={cyan:0,violet:100,amber:200}[selected];if(!owned.includes(selected)){if(save.coins<cost){$('skin-label').textContent=`需要 ${cost} 星币，当前 ${save.coins} 星币`;return;}save.coins-=cost;owned.push(selected);}skin=selected;persist();refreshSkin();}));
 $('start').onclick=start;$('again').onclick=start;$('restart').onclick=start;$('pause').onclick=pause;$('resume').onclick=pause;$('missile').onclick=fireMissile;
 $('home').onclick=()=>{clearReview();state='menu';g=null;show('result',false);show('menu',true);$('status').textContent='待命中';$('score').textContent='000000';$('kills').textContent='0';$('time').textContent='00:00';$('combo').textContent='等待出击';};
 $('sound').onclick=()=>{sound=!sound;$('sound').textContent=`声音 ${sound?'ON':'OFF'}`;if(sound)beep(600,.12);};
 window.addEventListener('keydown',e=>{const k=e.key.length===1?e.key.toLowerCase():e.key;if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' ','w','a','s','d','p','Escape'].includes(k)){if(state==='playing'||state==='paused')e.preventDefault();if((k==='p'||k==='Escape')&&!e.repeat)pause();else keys.add(k);}});
 window.addEventListener('keyup',e=>keys.delete(e.key.length===1?e.key.toLowerCase():e.key));
 function point(e){const rect=canvas.getBoundingClientRect();pointer={x:(e.clientX-rect.left)*W/rect.width,y:(e.clientY-rect.top)*H/rect.height};}
 canvas.addEventListener('pointermove',e=>{if(state==='playing'&&(e.pointerType==='mouse'||e.buttons))point(e);});
 canvas.addEventListener('pointerdown',e=>{if(state==='playing'){canvas.setPointerCapture(e.pointerId);point(e);canvas.focus();}});canvas.addEventListener('pointerup',e=>{if(e.pointerType!=='mouse')pointer=null;});canvas.addEventListener('pointercancel',()=>pointer=null);canvas.addEventListener('pointerleave',()=>pointer=null);
 window.addEventListener('blur',()=>{keys.clear();pointer=null;if(state==='playing')pause();});document.addEventListener('visibilitychange',()=>{if(document.hidden&&state==='playing')pause();});
 $('ai-review').onclick=async()=>{
  if(!g||state!=='result')return;const current=g;clearReview();reviewAbort=new AbortController();const controller=reviewAbort;const timeout=setTimeout(()=>controller.abort(),65000);$('ai-review').disabled=true;$('ai-review').textContent='本地教官正在分析…';
  try{if(location.protocol==='file:')throw new Error('请使用启动脚本打开游戏，以连接本地模型。');const res=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({score:g.score,kills:g.kills,seconds:Math.floor(g.t),maxCombo:g.maxCombo,damage:g.damage,missilesUsed:g.usedMissiles,victory:g.bossKilled}),signal:controller.signal});const data=await res.json();if(!res.ok)throw new Error(data.error||'模型暂不可用');if(g!==current||state!=='result')return;$('review').textContent=data.text;$('review-source').textContent='Ollama · '+data.model;
  }catch(e){if(g===current&&state==='result'){$('review-source').textContent='本地规则分析';$('review').textContent+='\n\nAI 点评未完成：'+(e.name==='AbortError'?'请求超时，请确认 Ollama 已启动。':e.message);}}
  finally{clearTimeout(timeout);if(g===current&&state==='result'){$('ai-review').disabled=false;$('ai-review').textContent='重新请求 AI 点评 ↗';}}
 };
 function frame(t){const dt=Math.min((t-last)/1000||0,.04);last=t;if(state!=='paused')bgTime+=dt;if(state==='playing')update(dt);draw(dt);if(bgTime>toastUntil)$('toast').classList.remove('show');requestAnimationFrame(frame);}
 updateSave();refreshSkin();requestAnimationFrame(frame);
})();
