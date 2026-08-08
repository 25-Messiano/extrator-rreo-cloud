const $ = id => document.getElementById(id);
const monthsG=["","Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];
const monthsM=["","Rúben","Simeão","Levi","Judá","Dã","Naftali","Gade","Aser","Issacar","Zebulom","Diná","José","Benjamim"];
const weekdayIndex={DOM:0,SEG:1,TER:2,QUA:3,QUI:4,SEX:5,SÁB:6};
const weekdayName={DOM:"Domingo",SEG:"Segunda-feira",TER:"Terça-feira",QUA:"Quarta-feira",QUI:"Quinta-feira",SEX:"Sexta-feira",SÁB:"Sábado"};

const defaultSettings={displayMode:"both",moon:true,seasons:true,easter:true,feasts:true};
let settings=loadSettings();
let selected=null;
let monthRecords={g:[],m:[]};
let limits={g:[-4000,3000],m:[-4010,3010]};
let timeState={level:"years",anchor:2026,type:"g"};
let dateSearchType="g";

function loadSettings(){try{return {...defaultSettings,...JSON.parse(localStorage.getItem("cm_settings")||"{}")}}catch{return {...defaultSettings}}}
function saveSettings(){localStorage.setItem("cm_settings",JSON.stringify(settings));applySettings();if(selected)renderAll(selected)}
async function json(url){const r=await fetch(url);const d=await r.json();if(!r.ok)throw new Error(d.erro||"Erro na consulta");return d}
function parseDate(s){const m=s.match(/^(\d{2})\/(\d{2})\/(-?\d+)(aC|dC)$/);return m?{day:+m[1],month:+m[2],yearNum:m[4]==="aC"?-Math.abs(+m[3]):Math.abs(+m[3]),yearLiteral:`${m[3]}${m[4]}`}:{day:0,month:0,yearNum:0,yearLiteral:""}}
function yearLabel(n){return n<0?`${Math.abs(n)} aC`:`${n} dC`}
function toast(msg){$("toast").textContent=msg;$("toast").classList.add("show");setTimeout(()=>$("toast").classList.remove("show"),2200)}

function visibleEvents(r){
  const out=[];
  for(const e of (r.eventos||[])){
    if(e.tipo==="lua"&&settings.moon)out.push({...e,kind:"moon"});
    if(e.tipo==="estacao"&&settings.seasons)out.push({...e,kind:"season"});
    if(e.tipo==="pascoa"&&settings.easter)out.push({...e,kind:"easter"});
  }
  if(settings.feasts){for(const f of (r.festas||[]))out.push({...f,tipo:"festa",kind:"feast"})}
  return out;
}
function moonClass(nome){const n=nome.toLowerCase();if(n.includes("crescente"))return "qc";if(n.includes("minguante"))return "qm";if(n.includes("cheia"))return "full";return "new"}
function markerHTML(ev){if(ev.kind==="moon")return `<i class="marker moon ${moonClass(ev.nome)}" title="${esc(ev.nome)}"></i>`;return `<i class="marker ${ev.kind}" title="${esc(ev.nome)}"></i>`}
function esc(s){return String(s||"").replace(/[&<>\"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}

function renderGrid(el,records,type){
  el.innerHTML="";
  if(!records.length){el.innerHTML='<div style="grid-column:1/-1;padding:18px;text-align:center;color:#777;font-size:12px">Sem registros</div>';return}
  const start=weekdayIndex[records[0].dia_semana]??0;
  for(let i=0;i<start;i++){const e=document.createElement("div");e.className="empty";el.appendChild(e)}
  for(const r of records){
    const d=parseDate(type==="g"?r.data_g:r.data_m), evs=visibleEvents(r);
    const b=document.createElement("button");b.className="day"+(selected&&r.id===selected.id?" selected":"");
    b.innerHTML=`<span class="day-num">${d.day}</span>${evs.length?`<span class="markers">${evs.slice(0,4).map(markerHTML).join("")}</span>`:""}`;
    b.title=evs.map(x=>x.nome).join(" · ")||`${type.toUpperCase()} ${type==="g"?r.data_g:r.data_m}`;
    b.onclick=()=>selectRecord(r.id);el.appendChild(b)
  }
}

function renderLegend(){
  const items=[];
  if(settings.moon)items.push('<span class="legend-item"><i class="marker moon qc"></i>Fases da Lua</span>');
  if(settings.seasons)items.push('<span class="legend-item"><i class="marker season"></i>Estações do Ano</span>');
  if(settings.easter)items.push('<span class="legend-item"><i class="marker easter"></i>Páscoa — 15 de Rúben</span>');
  if(settings.feasts)items.push('<span class="legend-item"><i class="marker feast"></i>Festas Bíblicas</span>');
  $("legend").innerHTML=items.join("")
}

function applySettings(){
  $("mCard").style.display=settings.displayMode==="g"?"none":"block";
  $("gCard").style.display=settings.displayMode==="m"?"none":"block";
  $("calendars").classList.toggle("single",settings.displayMode!=="both");
  document.querySelectorAll('.same-g').forEach(x=>x.style.display=settings.displayMode==="m"?"none":"flex");
  document.querySelectorAll('.same-m').forEach(x=>x.style.display=settings.displayMode==="g"?"none":"flex");
  document.querySelectorAll('.swap').forEach(x=>x.style.display=settings.displayMode==="both"?"inline":"none");
  renderLegend();
}

async function loadMonth(type,month,yearNum){return (await json(`/api/mes/${type}?mes=${month}&ano_num=${yearNum}`)).registros}
async function renderAll(r){
  selected=r;
  $("gValue").textContent=r.data_g;$("mValue").textContent=r.data_m;$("weekday").textContent=weekdayName[r.dia_semana]||r.dia_semana;
  const evs=visibleEvents(r);$("selectedEvents").innerHTML=evs.map(e=>`<span class="event-chip">${esc(e.nome)}</span>`).join("");
  const g=parseDate(r.data_g),m=parseDate(r.data_m);
  $("gTitle").textContent=`${monthsG[g.month]} · ${yearLabel(g.yearNum)}`;$("mTitle").textContent=`${monthsM[m.month]} · ${yearLabel(m.yearNum)}`;
  const focus=settings.displayMode==="m"?{type:"m",d:m}:{type:"g",d:g};
  $("periodTitle").textContent=`${focus.type==="g"?monthsG[focus.d.month]:monthsM[focus.d.month]} · ${yearLabel(focus.d.yearNum)}`;
  [monthRecords.g,monthRecords.m]=await Promise.all([loadMonth("g",g.month,g.yearNum),loadMonth("m",m.month,m.yearNum)]);
  renderGrid($("gGrid"),monthRecords.g,"g");renderGrid($("mGrid"),monthRecords.m,"m");applySettings();
}
async function selectRecord(id){try{await renderAll(await json(`/api/registro/${id}`))}catch(e){toast(e.message)}}
async function today(){try{await renderAll(await json('/api/hoje'))}catch(e){toast(e.message)}}

async function moveMonth(dir){
  if(!selected)return;
  const type=settings.displayMode==="m"?"m":"g";const records=monthRecords[type];if(!records.length)return;
  const edge=dir>0?records[records.length-1].id+1:records[0].id-1;if(edge<1)return;
  try{await selectRecord(edge)}catch{}
}

function openTime(){
  if(!selected)return;const type=settings.displayMode==="m"?"m":"g";const d=parseDate(type==="g"?selected.data_g:selected.data_m);
  timeState={level:"years",anchor:d.yearNum,type};$("timeModal").classList.add("open");$("timeModal").setAttribute("aria-hidden","false");renderTimeGrid()
}
function closeTime(){$("timeModal").classList.remove("open");$("timeModal").setAttribute("aria-hidden","true")}
function rangeStart(value,size,count=12){const span=size*count;return Math.floor(value/span)*span}
function renderTimeGrid(){
  const {level,anchor,type}=timeState;const min=limits[type][0],max=limits[type][1];let size,count=12,title="",start;
  if(level==="years"){size=1;title="Anos";start=rangeStart(anchor,1,12)}
  else if(level==="decades"){size=10;title="Décadas";start=rangeStart(anchor,10,12)}
  else if(level==="centuries"){size=100;title="Séculos";start=rangeStart(anchor,100,12)}
  else{size=1000;title="Grandes intervalos";count=8;start=Math.floor(min/1000)*1000}
  $("timeLevelTitle").textContent=title;$("timeRangeTitle").textContent=`${yearLabel(Math.max(start,min))} — ${yearLabel(Math.min(start+size*count-1,max))}`;
  const html=[];for(let i=0;i<count;i++){const a=start+i*size,b=a+size-1;if(b<min||a>max)continue;const aa=Math.max(a,min),bb=Math.min(b,max);let label=size===1?yearLabel(a):`${yearLabel(aa)} — ${yearLabel(bb)}`;html.push(`<button class="time-option ${anchor>=a&&anchor<=b?'current':''}" data-start="${a}" data-size="${size}">${label}</button>`)}
  $("timeGrid").innerHTML=html.join("");
  $("timeGrid").querySelectorAll(".time-option").forEach(b=>b.onclick=async()=>{const a=+b.dataset.start,s=+b.dataset.size;if(s===1){await jumpToYear(type,a);closeTime()}else{timeState.anchor=Math.max(a,min);timeState.level=s===1000?"centuries":s===100?"decades":"years";renderTimeGrid()}})
}
function timeUp(){const order=["years","decades","centuries","intervals"];const i=order.indexOf(timeState.level);if(i<order.length-1){timeState.level=order[i+1];renderTimeGrid()}}

async function jumpToYear(type,yearNum){
  try{const info=await json(`/api/ano/${type}?ano_num=${yearNum}`);const preferred=selected?parseDate(type==="g"?selected.data_g:selected.data_m).month:1;const month=info.meses.some(x=>x.mes===preferred)?preferred:info.meses[0].mes;const recs=await loadMonth(type,month,yearNum);if(!recs.length)throw new Error("Ano sem registros.");await selectRecord(recs[0].id)}catch(e){throw e}
}

function openYear(){const type=settings.displayMode==="m"?"m":"g";$("yearCalendar").value=type;$("yearInput").value="";$("yearMessage").textContent="";$("yearModal").classList.add("open");setTimeout(()=>$("yearInput").focus(),50)}
function closeYear(){$("yearModal").classList.remove("open")}
async function goYear(){const raw=$("yearInput").value.trim();const n=Number(raw);if(!Number.isInteger(n)){yearError("Informe um ano inteiro.");return}try{await jumpToYear($("yearCalendar").value,n);closeYear()}catch(e){yearError(e.message)}}
function yearError(msg){$("yearMessage").className="message error";$("yearMessage").textContent=msg}

function showPage(name){document.querySelectorAll(".app-page").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===name));$({calendar:"pageCalendar",reports:"pageReports",search:"pageSearch",settings:"pageSettings"}[name]).classList.add("active");$("topSubtitle").textContent={calendar:"Gregoriano ↔ Messiano",reports:"Relatórios em PDF",search:"Consulta externa",settings:"Preferências"}[name];closeDrawer()}
function openDrawer(){$("drawer").classList.add("open");$("overlay").classList.add("open")}
function closeDrawer(){$("drawer").classList.remove("open");$("overlay").classList.remove("open")}


function setDateSearchType(type){
  dateSearchType=type;$("dateTabG").classList.toggle("active",type==="g");$("dateTabM").classList.toggle("active",type==="m");
  $("dateSearchInput").placeholder=type==="g"?"Ex.: 08/08/2026dC":"Ex.: 28/09/2036dC";
}
async function searchOfficialDate(){
  const v=$("dateSearchInput").value.trim();if(!v)return;
  $("dateSearchMessage").className="message";$("dateSearchMessage").textContent="Consultando o registro oficial…";
  try{const r=await json(`/api/${dateSearchType}?data=${encodeURIComponent(v)}`);await renderAll(r);$("dateSearchMessage").textContent="Registro exato encontrado."}
  catch(e){$("dateSearchMessage").className="message error";$("dateSearchMessage").textContent=e.message}
}

async function webSearch(){const q=$("webSearchInput").value.trim();if(!q)return;$("webSearchMessage").className="message";$("webSearchMessage").textContent="Pesquisando…";$("webResults").innerHTML="";try{const d=await json(`/api/pesquisa?q=${encodeURIComponent(q)}`);$("webSearchMessage").textContent=d.aviso||`${d.resultados.length} resultado(s).`;let html=d.resultados.map(r=>`<article class="result-card card"><a href="${esc(r.link)}" target="_blank" rel="noopener noreferrer">${esc(r.titulo)}</a><p>${esc(r.resumo)}</p><small>${esc(r.fonte)}</small></article>`).join("");html+=`<a class="google-open" href="${esc(d.google_url)}" target="_blank" rel="noopener noreferrer">Abrir pesquisa no Google ↗</a>`;$("webResults").innerHTML=html}catch(e){$("webSearchMessage").className="message error";$("webSearchMessage").textContent=e.message}}


function reportReference(){return document.querySelector('input[name="reportRef"]:checked')?.value||"g"}
function fillReportMonths(){
  const ref=reportReference(), max=ref==="m"?13:12, names=ref==="m"?monthsM:monthsG, old=+$('reportMonth').value||1;
  $('reportMonth').innerHTML=Array.from({length:max},(_,i)=>`<option value="${i+1}">${String(i+1).padStart(2,'0')} · ${names[i+1]}</option>`).join('');
  $('reportMonth').value=Math.min(old,max);
}
function syncReportDefaults(){
  document.querySelectorAll('input[name="reportCalendarMode"]').forEach(x=>x.checked=x.value===settings.displayMode);
  if(!selected)return;const ref=reportReference();const d=parseDate(ref==="g"?selected.data_g:selected.data_m);
  $('reportYear').value=d.yearNum;$('reportMonth').value=d.month;$('reportDate').value=ref==="g"?selected.data_g:selected.data_m;
}
function updateReportForm(){
  const type=$('reportType').value;
  const yearTypes=new Set(['mensal','anual','lua','estacoes']);
  const monthTypes=new Set(['mensal']);
  const dateTypes=new Set(['data']);
  const rangeTypes=new Set(['correspondencia','intervalo']);
  $('reportReferenceBlock').style.display=type==='auditoria'||type==='festas'?'none':'grid';
  $('reportCalendarModeBlock').style.display=['correspondencia','lua','estacoes','festas','auditoria'].includes(type)?'none':'grid';
  $('reportYearBlock').style.display=yearTypes.has(type)?'grid':'none';
  $('reportMonthBlock').style.display=monthTypes.has(type)?'grid':'none';
  $('reportDateBlock').style.display=dateTypes.has(type)?'grid':'none';
  $('reportRangeBlock').style.display=rangeTypes.has(type)?'grid':'none';
  $('reportMarkersBlock').style.display=['mensal','anual','data','intervalo','festas'].includes(type)?'grid':'none';
}
function reportPayload(){
  return {
    tipo:$('reportType').value,
    calendario:document.querySelector('input[name="reportCalendarMode"]:checked')?.value||settings.displayMode,
    referencia:reportReference(),
    ano:$('reportYear').value.trim(),
    mes:$('reportMonth').value,
    data:$('reportDate').value.trim(),
    inicio:$('reportStart').value.trim(),
    fim:$('reportEnd').value.trim(),
    lua:$('reportMoon').checked,
    estacoes:$('reportSeasons').checked,
    pascoa:$('reportEaster').checked,
    festas:$('reportFeasts').checked,
  }
}
function filenameFromDisposition(header){const m=(header||'').match(/filename\*?=(?:UTF-8''|\")?([^\";]+)/i);return m?decodeURIComponent(m[1].replace(/\"/g,'')):'calendario_messiano_relatorio.pdf'}
async function generateReport(){
  const button=$('generateReportButton'), message=$('reportMessage');button.disabled=true;button.textContent='Gerando PDF…';message.className='message';message.textContent='Preparando o relatório com os registros oficiais…';
  try{
    const r=await fetch('/api/relatorios/pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reportPayload())});
    if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.erro||'Não foi possível gerar o PDF.');}
    const blob=await r.blob(), url=URL.createObjectURL(blob), a=document.createElement('a');a.href=url;a.download=filenameFromDisposition(r.headers.get('Content-Disposition'));document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);message.textContent='PDF gerado. O download foi iniciado.';
  }catch(e){message.className='message error';message.textContent=e.message}
  finally{button.disabled=false;button.textContent='Gerar PDF'}
}

function initSettingsUI(){
  document.querySelectorAll('input[name="displayMode"]').forEach(x=>{x.checked=x.value===settings.displayMode;x.onchange=()=>{settings.displayMode=x.value;saveSettings()}});
  const map={cfgMoon:"moon",cfgSeasons:"seasons",cfgEaster:"easter",cfgFeasts:"feasts"};for(const [id,key] of Object.entries(map)){$(id).checked=!!settings[key];$(id).onchange=()=>{settings[key]=$(id).checked;saveSettings()}}
}

$("openMenu").onclick=openDrawer;$("closeMenu").onclick=$("overlay").onclick=closeDrawer;document.querySelectorAll(".nav-item").forEach(b=>b.onclick=()=>showPage(b.dataset.page));
$("prevMonth").onclick=()=>moveMonth(-1);$("nextMonth").onclick=()=>moveMonth(1);$("periodButton").onclick=openTime;$("timeLevelTitle").parentElement.onclick=timeUp;
$("timeBack").onclick=()=>{const order=["years","decades","centuries","intervals"];const i=order.indexOf(timeState.level);if(i>0){timeState.level=order[i-1];renderTimeGrid()}else closeTime()};document.querySelectorAll("[data-close-modal]").forEach(x=>x.onclick=closeTime);
$("goYearButton").onclick=openYear;document.querySelectorAll("[data-close-year]").forEach(x=>x.onclick=closeYear);$("goYearConfirm").onclick=goYear;$("yearInput").onkeydown=e=>{if(e.key==="Enter")goYear()};
$("todayButton").onclick=$("todayTop").onclick=async()=>{showPage("calendar");await today()};
$("dateTabG").onclick=()=>setDateSearchType("g");$("dateTabM").onclick=()=>setDateSearchType("m");$("dateSearchButton").onclick=searchOfficialDate;$("dateSearchInput").onkeydown=e=>{if(e.key==="Enter")searchOfficialDate()};
$("webSearchButton").onclick=webSearch;$("webSearchInput").onkeydown=e=>{if(e.key==="Enter")webSearch()};
$("reportType").onchange=updateReportForm;document.querySelectorAll('input[name="reportRef"]').forEach(x=>x.onchange=()=>{fillReportMonths();syncReportDefaults()});$("generateReportButton").onclick=generateReport;

(async function boot(){initSettingsUI();applySettings();fillReportMonths();updateReportForm();try{const h=await json('/api/saude');limits=h.limites||limits}catch{}await today();syncReportDefaults()})()
