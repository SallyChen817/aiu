(function(root){
 'use strict';
 const finite=v=>typeof v==='number'&&Number.isFinite(v)?Math.max(0,Math.floor(v)):0;
 const cleanSave=s=>({best:finite(s?.best),coins:finite(s?.coins),plays:finite(s?.plays)});
 const api={
  multiplier:combo=>Math.min(3,1+Math.floor(Math.max(0,combo-1)/5)*0.5),
  points:(type,combo)=>Math.round(({scout:100,swift:200,heavy:500,boss:3000}[type]||0)*api.multiplier(combo)),
  hit:(a,b)=>(a.x-b.x)**2+(a.y-b.y)**2<=(a.r+b.r)**2,
  cleanSave,
  settle:(s,score)=>{s=cleanSave(s);score=finite(score);return {best:Math.max(s.best,score),coins:s.coins+Math.floor(score/100),plays:s.plays+1};}
 };
 if(typeof module!=='undefined')module.exports=api;else root.GameCore=api;
})(globalThis);
