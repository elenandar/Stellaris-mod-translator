"""Autonomous schema-v2 full-candidate editorial review interface."""

from __future__ import annotations


FULL_REVIEW_HTML_SHELL = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; font-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; form-action 'none'; base-uri 'none'; manifest-src 'none'">
<title>Stellaris Editorial Review</title>
<style>
:root{color-scheme:dark;--bg:#10141d;--panel:#171d29;--line:#2b3445;--text:#edf1f7;--muted:#98a4b8;--accent:#7bd7c4;--warn:#f4c56b;--bad:#ff8d91}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,sans-serif}
button,input,select,textarea{font:inherit}button,select,input,textarea{color:var(--text);background:#111722;border:1px solid var(--line);border-radius:8px}
button{padding:.55rem .8rem;cursor:pointer}button:hover:not(:disabled){border-color:var(--accent)}button:disabled{cursor:not-allowed;opacity:.45}
main{max-width:1500px;margin:auto;padding:18px}.top{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.title{font-size:1.35rem;font-weight:700}.muted{color:var(--muted)}.summary{margin-top:4px}.progress{height:10px;background:#242c3a;border-radius:8px;overflow:hidden;min-width:220px}.progress>span{display:block;height:100%;background:var(--accent)}
.filters{display:grid;grid-template-columns:minmax(230px,2fr) repeat(4,minmax(135px,1fr));gap:10px;margin:16px 0}.filters input,.filters select{padding:.6rem}.attention{display:flex;align-items:center;gap:7px;padding:.55rem;border:1px solid var(--line);border-radius:8px;background:#111722}
.results{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:-6px 0 10px}.pager{display:flex;align-items:center;gap:8px}
.layout{display:grid;grid-template-columns:minmax(250px,330px) 1fr;gap:14px}.list{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px;max-height:76vh;overflow:auto}
.list button{width:100%;text-align:left;margin-bottom:6px;white-space:pre-line}.list button.active{border-color:var(--accent);background:#1b2b30}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.metadata{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);margin-bottom:12px}.status{color:var(--warn)}.warnings{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.warning-chip{display:inline-block;padding:2px 7px;border:1px solid #816d3e;border-radius:6px;color:var(--warn);background:#2d281d}.accept-warning{padding:10px;border:1px solid #816d3e;border-radius:8px;background:#2d281d;color:var(--warn);margin:10px 0}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:12px}.spanbox{min-height:130px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#111722;border:1px solid var(--line);border-radius:9px}
.atom{display:inline-block;padding:1px 6px;margin:1px 2px;border:1px solid #52706d;border-radius:5px;color:var(--accent);background:#172725;font-family:ui-monospace,monospace}
.field{margin-top:14px}.field>label{display:block;font-weight:650;margin-bottom:6px}.editor{display:flex;flex-wrap:wrap;align-items:stretch;gap:6px}.editor textarea{min-height:84px;min-width:170px;flex:1;padding:9px;resize:vertical}
.decision-row,.tag-row,.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.decision-row select,.field textarea{padding:9px;width:100%}.tag-row label{font-weight:400}
.actions{justify-content:space-between;margin-top:16px}.error{color:var(--bad);min-height:1.4em}.storage-warning{color:var(--bad);padding:8px 0}.help{margin:12px 0;padding:12px;border:1px solid var(--line);border-radius:9px;background:#111722}.help kbd{border:1px solid var(--line);border-radius:4px;padding:1px 5px}.hidden{display:none!important}
@media(max-width:1000px){.filters{grid-template-columns:1fr 1fr 1fr}.layout,.columns{grid-template-columns:1fr}.list{max-height:260px}}
@media(max-width:650px){.filters{grid-template-columns:1fr}.results{align-items:flex-start;flex-direction:column}}
</style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <div class="title">Локальный editorial review</div>
      <div class="muted" id="fingerprint">Pack __PACK_FINGERPRINT__</div>
      <div class="muted summary" id="scopeSummary"></div>
    </div>
    <div><div id="progressText"></div><div class="progress"><span id="progressBar"></span></div></div>
  </div>
  <div class="storage-warning hidden" id="storageWarning" role="alert"></div>
  <div class="help hidden" id="helpPanel">
    <strong>Клавиши вне полей ввода</strong>:
    <kbd>A</kbd> принять, <kbd>E</kbd> редактировать,
    <kbd>R</kbd> отклонить, <kbd>U</kbd> вернуть без решения,
    <kbd>J</kbd>/<kbd>K</kbd> или стрелки — навигация,
    <kbd>/</kbd> — поиск, <kbd>?</kbd> — эта справка.
    <button id="closeHelp" type="button">Закрыть</button>
  </div>
  <div class="filters">
    <input id="search" type="search" placeholder="Поиск по файлу, оригиналу или переводу">
    <label class="attention"><input id="attentionFilter" type="checkbox"> Требует внимания</label>
    <select id="fileFilter"><option value="">Все файлы</option></select>
    <select id="statusFilter">
      <option value="">Все статусы</option>
      <option value="accepted_changed">Перевод изменён</option>
      <option value="accepted_unchanged">Оставлен английский</option>
      <option value="model_fallback">Fallback модели</option>
    </select>
    <select id="decisionFilter">
      <option value="">Все решения</option>
      <option value="unreviewed">Без решения</option>
      <option value="accept">Принять</option>
      <option value="edit">Редактировать</option>
      <option value="reject">Отклонить</option>
    </select>
    <select id="warningFilter">
      <option value="">Все предупреждения</option>
      <option value="model_fallback">Fallback модели</option>
      <option value="accepted_unchanged">Оставлен английский</option>
      <option value="leading_boundary_whitespace_changed">Изменён ведущий пробел</option>
      <option value="trailing_boundary_whitespace_changed">Изменён завершающий пробел</option>
    </select>
  </div>
  <div class="results">
    <span id="resultCount"></span>
    <div class="pager">
      <button id="pagePrevious" type="button">← Страница</button>
      <span id="pageInfo"></span>
      <button id="pageNext" type="button">Страница →</button>
    </div>
  </div>
  <div class="layout">
    <nav class="list" id="entryList" aria-label="Occurrences"></nav>
    <section class="card">
      <div id="empty">Нет записей для выбранного фильтра.</div>
      <div id="review" class="hidden">
        <div class="metadata"><span id="path"></span><span id="line"></span><span class="status" id="status"></span></div>
        <div class="warnings" id="warnings"></div>
        <div class="accept-warning hidden" id="acceptWarning">Принять здесь означает сохранить английский текст. Для перевода выберите «Редактировать».</div>
        <div class="columns">
          <div><strong>Оригинал</strong><div class="spanbox" id="sourceText"></div></div>
          <div><strong>Candidate</strong><div class="spanbox" id="candidateText"></div></div>
        </div>
        <div class="field"><label>Protected atoms / escapes</label><div id="atoms"></div></div>
        <div class="field decision-row"><label for="decision">Решение</label>
          <select id="decision">
            <option value="unreviewed">Без решения</option>
            <option value="accept">Принять</option>
            <option value="edit">Редактировать</option>
            <option value="reject">Отклонить</option>
          </select>
        </div>
        <div class="field" id="editorField"><label>Итоговый русский вариант</label><div class="editor" id="editor"></div></div>
        <div class="field"><label for="note">Комментарий</label><textarea id="note" rows="3"></textarea></div>
        <div class="field"><label>Теги</label><div class="tag-row" id="tags"></div></div>
        <div class="field"><label><input type="checkbox" id="glossary"> Кандидат в глоссарий</label></div>
        <div class="actions">
          <div><button id="previous" type="button">← Предыдущая</button> <button id="next" type="button">Следующая →</button></div>
          <div>
            <button id="draftExport" type="button">Экспорт черновика</button>
            <button id="finalExport" type="button" disabled>Финальный экспорт</button>
            <button id="importButton" type="button">Импорт JSON</button>
            <button id="helpButton" type="button">Справка</button>
            <button id="clear" type="button">Очистить решения</button>
            <input class="hidden" id="importFile" type="file" accept="application/json">
          </div>
        </div>
        <div class="error" id="error" role="alert"></div>
      </div>
    </section>
  </div>
</main>
<script id="review-data" type="application/octet-stream">__PACK_DATA_BASE64__</script>
<script>
"use strict";
const MAX_JSON_BYTES=4*1024*1024;
const PAGE_SIZE=100;
const TEXT_DEBOUNCE_MS=350;
const raw=document.getElementById("review-data").textContent.trim();
const bytes=Uint8Array.from(atob(raw),value=>value.charCodeAt(0));
const pack=JSON.parse(new TextDecoder().decode(bytes));
const allowedDecisions=new Set(["unreviewed","accept","edit","reject"]);
const allowedTags=new Set(["terminology","lore","meaning","style","grammar","leftover_english"]);
const allowedWarnings=new Set(["model_fallback","accepted_unchanged","leading_boundary_whitespace_changed","trailing_boundary_whitespace_changed"]);
const storageKey="stellaris-review-pack:"+pack.pack_fingerprint;
const byId=new Map(pack.entries.map(entry=>[entry.id,entry]));
const entryIndexById=new Map(pack.entries.map((entry,index)=>[entry.id,index]));
const statusLabels={
  accepted_changed:"Перевод изменён",
  accepted_unchanged:"Оставлен английский",
  model_fallback:"Fallback модели"
};
const decisionLabels={unreviewed:"Без решения",accept:"Принять",edit:"Редактировать",reject:"Отклонить"};
const warningLabels={
  model_fallback:"Fallback модели",
  accepted_unchanged:"Оставлен английский",
  leading_boundary_whitespace_changed:"Изменён ведущий пробел у human segment",
  trailing_boundary_whitespace_changed:"Изменён завершающий пробел у human segment"
};
let state=new Map();
const drafts=new Map();
let storageFailureMessage="";
let saveTimer=null;
let visible=[];
let pageIndex=0;
let currentId=pack.entries.length?pack.entries[0].id:null;
const el=id=>document.getElementById(id);
const defaults=record=>({decision:"unreviewed",edited_segments:record.candidate_segments.slice(),note:"",tags:[],glossary_candidate:false});
const cloneItem=item=>({decision:item.decision,edited_segments:item.edited_segments.slice(),note:item.note,tags:item.tags.slice(),glossary_candidate:item.glossary_candidate});
const currentState=record=>state.get(record.id)||defaults(record);
const renderedState=record=>drafts.has(record.id)?drafts.get(record.id).item:currentState(record);
function arraysEqual(left,right){return left.length===right.length&&left.every((value,index)=>value===right[index])}
function isDefaultItem(record,item){const baseline=defaults(record);return item.decision===baseline.decision&&arraysEqual(item.edited_segments,baseline.edited_segments)&&item.note===""&&item.tags.length===0&&item.glossary_candidate===false}
function normalizeSparseMap(value){const result=new Map();for(const [id,item] of value){const record=byId.get(id);if(!record)throw new Error("unknown occurrence ID");validateStoredItem(record,item);if(!isDefaultItem(record,item))result.set(id,cloneItem(item))}return result}
function appendSpan(container,segments,atoms){
  container.replaceChildren();
  segments.forEach((segment,index)=>{
    container.append(document.createTextNode(segment));
    if(index<atoms.length){const chip=document.createElement("span");chip.className="atom";chip.textContent=atoms[index];container.append(chip)}
  });
}
function fullTranslation(record,item){let result="";item.edited_segments.forEach((segment,index)=>{result+=segment;if(index<record.protected_atoms.length)result+=record.protected_atoms[index]});return result}
function validateUnicodeScalars(value,label){
  if(typeof value!=="string")throw new Error(label+" must be a string");
  for(let index=0;index<value.length;index++){
    const code=value.charCodeAt(index);
    if(code>=0xd800&&code<=0xdbff){const next=value.charCodeAt(index+1);if(!(next>=0xdc00&&next<=0xdfff))throw new Error(label+" contains invalid Unicode scalar");index++}
    else if(code>=0xdc00&&code<=0xdfff)throw new Error(label+" contains invalid Unicode scalar")
  }
}
function validateText(value){validateUnicodeScalars(value,"edited_translation");if(/[\u0000-\u001f\u007f-\u009f\u2028\u2029\ufeff]/u.test(value)||/\p{Cf}/u.test(value))throw new Error("edited_translation contains unsafe control")}
function validateSegment(value){validateText(value);if(/[$\[\]£§\\\\"]/u.test(value))throw new Error("edited_translation introduces protected syntax")}
function validateNote(value){validateUnicodeScalars(value,"note")}
function splitEdited(record,value){
  validateText(value);const segments=[];let cursor=0;
  for(const atom of record.protected_atoms){const position=value.indexOf(atom,cursor);if(position<0)throw new Error("protected atom mismatch");const segment=value.slice(cursor,position);validateSegment(segment);segments.push(segment);cursor=position+atom.length}
  const finalSegment=value.slice(cursor);validateSegment(finalSegment);segments.push(finalSegment);
  let rebuilt="";segments.forEach((segment,index)=>{rebuilt+=segment;if(index<record.protected_atoms.length)rebuilt+=record.protected_atoms[index]});
  if(rebuilt!==value)throw new Error("protected atom mismatch");return segments
}
function validateStoredItem(record,item){
  if(!item||typeof item!=="object"||Array.isArray(item)||!allowedDecisions.has(item.decision)||typeof item.glossary_candidate!=="boolean"||!Array.isArray(item.tags)||new Set(item.tags).size!==item.tags.length||item.tags.some(tag=>!allowedTags.has(tag)))throw new Error("invalid saved decision state");
  validateNote(item.note);
  if(!Array.isArray(item.edited_segments)||item.edited_segments.length!==record.protected_atoms.length+1)throw new Error("invalid saved edited segments");
  item.edited_segments.forEach(validateSegment);
  if(item.decision==="edit")splitEdited(record,fullTranslation(record,item))
}
function exactFields(object,fields){return Object.keys(object).sort().join("\n")===fields.slice().sort().join("\n")}
function decisionRecord(record,item){
  validateStoredItem(record,item);
  const result={occurrence_id:record.id,decision:item.decision,note:item.note,tags:item.tags.slice().sort(),glossary_candidate:item.glossary_candidate,source_span_sha256:record.source_span_sha256,candidate_span_sha256:record.candidate_span_sha256};
  if(item.decision==="edit")result.edited_translation=fullTranslation(record,item);
  return result
}
function validateDecisionRecord(item){
  if(!item||typeof item!=="object"||Array.isArray(item))throw new Error("invalid decision record");
  const record=byId.get(item.occurrence_id);if(!record)throw new Error("unknown occurrence ID");
  if(!allowedDecisions.has(item.decision))throw new Error("invalid decision enum");
  const fields=["occurrence_id","decision","note","tags","glossary_candidate","source_span_sha256","candidate_span_sha256"];if(item.decision==="edit")fields.push("edited_translation");
  if(!exactFields(item,fields))throw new Error("invalid decision fields");
  if(typeof item.note!=="string"||typeof item.glossary_candidate!=="boolean"||!Array.isArray(item.tags)||new Set(item.tags).size!==item.tags.length||item.tags.some(tag=>!allowedTags.has(tag)))throw new Error("invalid decision values");
  validateNote(item.note);
  if(item.source_span_sha256!==record.source_span_sha256||item.candidate_span_sha256!==record.candidate_span_sha256)throw new Error("span identity mismatch");
  const editedSegments=item.decision==="edit"?splitEdited(record,item.edited_translation):record.candidate_segments.slice();
  const normalized={decision:item.decision,edited_segments:editedSegments,note:item.note,tags:item.tags.slice(),glossary_candidate:item.glossary_candidate};
  validateStoredItem(record,normalized);return [record,normalized]
}
function exportDocument(stateValue=state,rejectDrafts=true,requireComplete=false){
  if(rejectDrafts&&[...drafts.values()].some(draft=>!draft.valid))throw new Error("исправьте невалидную редакцию перед экспортом");
  const decisions=pack.entries.map(record=>decisionRecord(record,stateValue.get(record.id)||defaults(record)));
  if(requireComplete&&decisions.some(item=>item.decision==="unreviewed"))throw new Error("финальный экспорт требует решения для каждой записи");
  return {schema_version:1,pack_fingerprint:pack.pack_fingerprint,decisions}
}
function validateDocument(documentValue){
  if(!documentValue||typeof documentValue!=="object"||Array.isArray(documentValue)||!exactFields(documentValue,["schema_version","pack_fingerprint","decisions"]))throw new Error("invalid decisions document fields");
  if(documentValue.schema_version!==1)throw new Error("invalid decisions schema");
  if(documentValue.pack_fingerprint!==pack.pack_fingerprint)throw new Error("fingerprint mismatch");
  if(!Array.isArray(documentValue.decisions))throw new Error("invalid decisions array");
  const next=new Map();const seen=new Set();
  for(const item of documentValue.decisions){const [record,normalized]=validateDecisionRecord(item);if(seen.has(record.id))throw new Error("duplicate occurrence ID");seen.add(record.id);if(!isDefaultItem(record,normalized))next.set(record.id,normalized)}
  return next
}
function sparseDocument(stateValue=state){
  const changes=[];for(const record of pack.entries){const item=stateValue.get(record.id);if(item){validateStoredItem(record,item);if(!isDefaultItem(record,item))changes.push(decisionRecord(record,item))}}
  return {storage_schema_version:1,pack_fingerprint:pack.pack_fingerprint,changes}
}
function validateSparseDocument(documentValue){
  if(!documentValue||typeof documentValue!=="object"||Array.isArray(documentValue)||!exactFields(documentValue,["storage_schema_version","pack_fingerprint","changes"]))throw new Error("invalid sparse storage document");
  if(documentValue.storage_schema_version!==1||documentValue.pack_fingerprint!==pack.pack_fingerprint||!Array.isArray(documentValue.changes))throw new Error("invalid sparse storage identity");
  const next=new Map();for(const item of documentValue.changes){const [record,normalized]=validateDecisionRecord(item);if(next.has(record.id))throw new Error("duplicate occurrence ID");if(!isDefaultItem(record,normalized))next.set(record.id,normalized)}return next
}
function renderStorageWarning(){el("storageWarning").textContent=storageFailureMessage;el("storageWarning").classList.toggle("hidden",!storageFailureMessage)}
function persistSparse(){
  try{localStorage.setItem(storageKey,JSON.stringify(sparseDocument()));return true}
  catch(error){storageFailureMessage="Локальное сохранение недоступно. Валидные решения остаются в памяти и доступны для экспорта: "+error.message;renderStorageWarning();return false}
}
function save(nextState=state){state=normalizeSparseMap(nextState);persistSparse();updateProgress()}
function setStateMemory(record,item){validateStoredItem(record,item);const next=new Map(state);if(isDefaultItem(record,item))next.delete(record.id);else next.set(record.id,cloneItem(item));state=next}
function persistRecord(record,item){setStateMemory(record,item);persistSparse();updateProgress()}
function scheduleTextSave(){if(saveTimer!==null)clearTimeout(saveTimer);saveTimer=setTimeout(()=>flushText(),TEXT_DEBOUNCE_MS)}
function flushText(){
  if(saveTimer!==null){clearTimeout(saveTimer);saveTimer=null}
  for(const [id,draft] of [...drafts])if(draft.valid)drafts.delete(id);
  persistSparse();updateProgress()
}
function updateDraft(record,item){
  const draft={item:cloneItem(item),valid:true,error:""};
  try{validateStoredItem(record,draft.item);setStateMemory(record,draft.item);showError("")}
  catch(error){draft.valid=false;draft.error=error.message;showError("Редактирование отклонено: "+error.message)}
  drafts.set(record.id,draft);scheduleTextSave();updateProgress()
}
function showError(message){el("error").textContent=message}
function updateDraftAwareField(record,field,value,persistImmediately=false){
  const fieldValue=Array.isArray(value)?value.slice():value;const item=cloneItem(currentState(record));item[field]=fieldValue;setStateMemory(record,item);
  const draft=drafts.get(record.id);if(draft)draft.item[field]=Array.isArray(fieldValue)?fieldValue.slice():fieldValue;
  if(persistImmediately)persistSparse();else scheduleTextSave();updateProgress();
  if(draft&&!draft.valid)showError("Редактирование отклонено: "+draft.error);else showError("")
}
function reviewedCount(){let count=0;for(const record of pack.entries)if(currentState(record).decision!=="unreviewed")count++;return count}
function updateProgress(){
  const reviewed=reviewedCount();el("progressText").textContent=reviewed+" / "+pack.entries.length+" проверено";el("progressBar").style.width=(pack.entries.length?reviewed/pack.entries.length*100:0)+"%";
  const hasInvalid=[...drafts.values()].some(draft=>!draft.valid);el("finalExport").disabled=reviewed!==pack.entries.length||hasInvalid
}
function searchable(record){return [record.path,record.status,...record.source_segments,...record.candidate_segments].join("\n").toLocaleLowerCase()}
function needsAttention(record){return record.status==="model_fallback"||record.status==="accepted_unchanged"||record.warnings.some(warning=>warning==="leading_boundary_whitespace_changed"||warning==="trailing_boundary_whitespace_changed")}
function applyFilters(keepEmpty=false,preserveCurrent=false){
  const query=el("search").value.toLocaleLowerCase();const file=el("fileFilter").value;const status=el("statusFilter").value;const decision=el("decisionFilter").value;const warning=el("warningFilter").value;const attention=el("attentionFilter").checked;
  visible=pack.entries.filter(record=>(!file||record.path===file)&&(!status||record.status===status)&&(!decision||currentState(record).decision===decision)&&(!warning||record.warnings.includes(warning))&&(!attention||needsAttention(record))&&(!query||searchable(record).includes(query)));
  const visibleIndex=visible.findIndex(record=>record.id===currentId);if(visibleIndex<0){if(!keepEmpty&&!preserveCurrent)currentId=visible.length?visible[0].id:null;pageIndex=0}else pageIndex=Math.floor(visibleIndex/PAGE_SIZE);
  render()
}
function renderList(){
  const list=el("entryList");list.replaceChildren();const pageCount=Math.max(1,Math.ceil(visible.length/PAGE_SIZE));if(pageIndex>=pageCount)pageIndex=pageCount-1;
  const start=pageIndex*PAGE_SIZE;for(const record of visible.slice(start,start+PAGE_SIZE)){const button=document.createElement("button");button.type="button";button.className=record.id===currentId?"active":"";const item=currentState(record);button.textContent=record.path+" · строка "+record.line+"\n"+statusLabels[record.status]+" · "+decisionLabels[item.decision];button.addEventListener("click",()=>{flushText();currentId=record.id;render()});list.append(button)}
  el("resultCount").textContent="Найдено: "+visible.length;el("pageInfo").textContent=visible.length?"Страница "+(pageIndex+1)+" / "+pageCount:"Страница 0 / 0";el("pagePrevious").disabled=pageIndex<=0;el("pageNext").disabled=pageIndex>=pageCount-1
}
function renderEditor(record,item){
  const editor=el("editor");editor.replaceChildren();const rendered=renderedState(record);
  rendered.edited_segments.forEach((segment,index)=>{const area=document.createElement("textarea");area.value=segment;area.setAttribute("aria-label","Редактируемый human segment "+(index+1));area.addEventListener("input",()=>{const next=cloneItem(renderedState(record));next.edited_segments[index]=area.value;updateDraft(record,next)});area.addEventListener("blur",flushText);editor.append(area);if(index<record.protected_atoms.length){const atom=document.createElement("span");atom.className="atom";atom.textContent=record.protected_atoms[index];editor.append(atom)}})
}
function render(){
  renderList();updateProgress();renderStorageWarning();const record=byId.get(currentId);el("empty").classList.toggle("hidden",Boolean(record));el("review").classList.toggle("hidden",!record);if(!record)return;
  const item=renderedState(record);el("path").textContent=record.path;el("line").textContent="строка "+record.line;el("status").textContent=statusLabels[record.status]+" ("+record.status+")";
  const warnings=el("warnings");warnings.replaceChildren();for(const warning of record.warnings){const chip=document.createElement("span");chip.className="warning-chip";chip.textContent=warningLabels[warning]+" ("+warning+")";warnings.append(chip)}
  el("acceptWarning").classList.toggle("hidden",record.status!=="model_fallback"&&record.status!=="accepted_unchanged");
  appendSpan(el("sourceText"),record.source_segments,record.protected_atoms);appendSpan(el("candidateText"),record.candidate_segments,record.protected_atoms);
  const atoms=el("atoms");atoms.replaceChildren();if(!record.protected_atoms.length)atoms.textContent="Нет";for(const value of record.protected_atoms){const chip=document.createElement("span");chip.className="atom";chip.textContent=value;atoms.append(chip)}
  el("decision").value=item.decision;el("note").value=item.note;el("glossary").checked=item.glossary_candidate;el("editorField").classList.toggle("hidden",item.decision!=="edit");renderEditor(record,item);
  for(const input of el("tags").querySelectorAll("input"))input.checked=item.tags.includes(input.value)
}
function neighboringVisibleRecord(delta){
  const index=visible.findIndex(record=>record.id===currentId);if(index>=0){const next=index+delta;return next>=0&&next<visible.length?visible[next]:null}
  const currentIndex=entryIndexById.get(currentId);if(currentIndex===undefined)return null;const candidates=delta>0?visible:[...visible].reverse();return candidates.find(value=>delta>0?entryIndexById.get(value.id)>currentIndex:entryIndexById.get(value.id)<currentIndex)||null
}
function move(delta){
  flushText();const record=neighboringVisibleRecord(delta);if(!record)return;currentId=record.id;pageIndex=Math.floor(visible.findIndex(value=>value.id===record.id)/PAGE_SIZE);render()
}
function setDecision(decision,advance=false){
  const record=byId.get(currentId);if(!record)return;const nextRecord=neighboringVisibleRecord(1);flushText();const item=cloneItem(currentState(record));item.decision=decision;if(decision!=="edit"){item.edited_segments=record.candidate_segments.slice();drafts.delete(record.id)}persistRecord(record,item);if(advance){const decisionFilter=el("decisionFilter").value;if(decisionFilter&&decision!==decisionFilter){if(nextRecord)currentId=nextRecord.id;applyFilters(false,!nextRecord)}else move(1)}else{applyFilters(false,decision==="edit");if(decision==="edit"){const area=el("editor").querySelector("textarea");if(area)area.focus()}}
}
function documentBytes(documentValue){const text=JSON.stringify(documentValue,null,2).replace(/\n+$/u,"")+"\n";const encoded=new TextEncoder().encode(text);if(encoded.byteLength>MAX_JSON_BYTES)throw new Error("JSON превышает лимит 4 MiB");return encoded}
function downloadDocument(finalMode){
  flushText();const documentValue=exportDocument(state,finalMode,finalMode);const encoded=documentBytes(documentValue);const blob=new Blob([encoded],{type:"application/json"});const link=document.createElement("a");link.download=(finalMode?"review-decisions-final-":"review-decisions-draft-")+pack.pack_fingerprint.slice(0,12)+".json";link.href=URL.createObjectURL(blob);link.click();setTimeout(()=>URL.revokeObjectURL(link.href),0)
}
for(const file of [...new Set(pack.entries.map(record=>record.path))].sort()){const option=document.createElement("option");option.value=file;option.textContent=file;el("fileFilter").append(option)}
for(const tag of allowedTags){const label=document.createElement("label");const input=document.createElement("input");input.type="checkbox";input.value=tag;input.addEventListener("change",()=>{const record=byId.get(currentId);if(!record)return;const tags=[...el("tags").querySelectorAll("input:checked")].map(node=>node.value);try{updateDraftAwareField(record,"tags",tags,true)}catch(error){render();showError("Изменение отклонено: "+error.message)}});label.append(input,document.createTextNode(" "+tag));el("tags").append(label)}
for(const id of ["search","attentionFilter","fileFilter","statusFilter","decisionFilter","warningFilter"])el(id).addEventListener(id==="search"?"input":"change",()=>applyFilters());
el("decision").addEventListener("change",()=>setDecision(el("decision").value));
el("note").addEventListener("input",()=>{const record=byId.get(currentId);if(!record)return;try{updateDraftAwareField(record,"note",el("note").value)}catch(error){render();showError("Комментарий отклонён: "+error.message)}});
el("note").addEventListener("blur",flushText);
el("glossary").addEventListener("change",()=>{const record=byId.get(currentId);if(!record)return;try{updateDraftAwareField(record,"glossary_candidate",el("glossary").checked,true)}catch(error){render();showError("Изменение отклонено: "+error.message)}});
el("previous").addEventListener("click",()=>move(-1));el("next").addEventListener("click",()=>move(1));
el("pagePrevious").addEventListener("click",()=>{flushText();if(pageIndex>0){pageIndex--;currentId=visible[pageIndex*PAGE_SIZE].id;render()}});
el("pageNext").addEventListener("click",()=>{flushText();if((pageIndex+1)*PAGE_SIZE<visible.length){pageIndex++;currentId=visible[pageIndex*PAGE_SIZE].id;render()}});
el("draftExport").addEventListener("click",()=>{try{downloadDocument(false);showError("")}catch(error){showError("Экспорт черновика отклонён: "+error.message)}});
el("finalExport").addEventListener("click",()=>{try{downloadDocument(true);showError("")}catch(error){showError("Финальный экспорт отклонён: "+error.message)}});
el("importButton").addEventListener("click",()=>el("importFile").click());
el("importFile").addEventListener("change",async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>MAX_JSON_BYTES)throw new Error("файл превышает лимит 4 MiB");const text=await file.text();if(new TextEncoder().encode(text).byteLength>MAX_JSON_BYTES)throw new Error("файл превышает лимит 4 MiB");const nextState=validateDocument(JSON.parse(text));state=nextState;drafts.clear();persistSparse();applyFilters();showError("")}catch(error){showError("Импорт отклонён: "+error.message)}finally{event.target.value=""}});
el("clear").addEventListener("click",()=>{if(confirm("Удалить все локальные решения для этого pack?")){state=new Map();drafts.clear();try{localStorage.removeItem(storageKey)}catch(error){storageFailureMessage="Локальное хранилище недоступно, но решения очищены в памяти: "+error.message}applyFilters();showError("")}});
function toggleHelp(force){const show=force===undefined?el("helpPanel").classList.contains("hidden"):force;el("helpPanel").classList.toggle("hidden",!show)}
el("helpButton").addEventListener("click",()=>toggleHelp());el("closeHelp").addEventListener("click",()=>toggleHelp(false));
function interactiveTarget(target){if(!target)return false;const tag=(target.tagName||"").toUpperCase();return ["INPUT","TEXTAREA","SELECT","BUTTON"].includes(tag)||target.isContentEditable}
document.addEventListener("keydown",event=>{if(interactiveTarget(event.target))return;const key=event.key;
  if(key==="/"){event.preventDefault();el("search").focus();return}
  if(key==="?"){event.preventDefault();toggleHelp();return}
  if(key==="a"||key==="A"){event.preventDefault();setDecision("accept",true)}
  else if(key==="e"||key==="E"){event.preventDefault();setDecision("edit",false)}
  else if(key==="r"||key==="R"){event.preventDefault();setDecision("reject",true)}
  else if(key==="u"||key==="U"){event.preventDefault();setDecision("unreviewed",false)}
  else if(key==="j"||key==="J"||key==="ArrowDown"||key==="ArrowRight"){event.preventDefault();move(1)}
  else if(key==="k"||key==="K"||key==="ArrowUp"||key==="ArrowLeft"){event.preventDefault();move(-1)}
});
if(typeof window!=="undefined")window.addEventListener("pagehide",flushText);
try{const saved=localStorage.getItem(storageKey);if(saved)state=validateSparseDocument(JSON.parse(saved))}
catch(error){state=new Map();storageFailureMessage="Локальное сохранение не загружено: "+error.message}
el("scopeSummary").textContent="Полный candidate · unsupported: "+pack.summary.unsupported+" · skipped files: "+pack.summary.skipped_files+" · whitespace warnings: "+pack.summary.whitespace_warning_entries;
applyFilters();
</script>
</body>
</html>
"""
