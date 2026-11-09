<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api,errorText,type Work,type Summary } from './api'

const works=ref<Work[]>([]), summary=ref<Summary>({reviewed:0,errors:[]})
const question=ref(''), selected=ref<number|null>(null), filter=ref('all')
const feedback=ref(''), tag=ref(''), verdict=ref(''), error=ref(''), notice=ref('')
const busy=ref(false)
const labels:Record<string,string>={queued:'等待批改', grading:'批改中', draft:'待复核', failed:'需人工批改', reviewed:'已反馈'}
const eligible=(w:Work)=>['draft','failed'].includes(w.state)
const pending=computed(()=>works.value.filter(eligible).length)
const visible=computed(()=>works.value.filter(w=>filter.value==='all' || (filter.value==='pending'?eligible(w):w.state==='reviewed')))
const item=computed(()=>works.value.find(w=>w.id===selected.value))
function select(w?:Work) {
  selected.value=w?.id??null
  const draft=w?.review||w?.draft
  verdict.value=draft?.verdict==='uncertain'?'':draft?.verdict||''
  tag.value=draft?.tag||'';feedback.value=draft?.feedback||''
}
function changeFilter(value:string) {filter.value=value;select(visible.value[0])}
async function load(preserve=true) {
  const [rows,stats,task]=await Promise.all([api<Work[]>('/submissions'),api<Summary>('/summary'),api<{prompt:string}>('/assignment')])
  const old=item.value
  works.value=rows;summary.value=stats;question.value=task.prompt
  const next=visible.value.find(w=>w.id===selected.value)||visible.value[0]
  if (!preserve || !next || old?.id!==next.id || old?.state!==next.state) select(next)
}
async function refresh() {
  if(busy.value)return
  busy.value=true;error.value='';notice.value=''
  try{await load()}catch(e){error.value=errorText(e)}finally{busy.value=false}
}
onMounted(refresh)
async function publish() {
  if(!item.value || busy.value)return
  const id=item.value.id
  busy.value=true;error.value='';notice.value=''
  try{
    await api('/submissions/'+id+'/review',{verdict:verdict.value,feedback:feedback.value.trim(),tag:verdict.value==='incorrect'?tag.value.trim():''})
    notice.value='反馈已发送给学生。';await load(false)
  }catch(e){error.value=errorText(e)}finally{busy.value=false}
}
const when=(s:number)=>new Date(s*1000).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})
</script>
<template><section>
  <header class="page-head"><div><h1>作业复核</h1><p class="muted">核对学生作答，将确认后的反馈发回小程序。</p></div><button class="secondary" :disabled="busy" @click="refresh">刷新作业</button></header>
  <div class="stats"><div><span>班级提交</span><strong>{{works.length}}</strong></div><div><span>待复核</span><strong>{{pending}}</strong></div><div><span>已反馈</span><strong>{{summary.reviewed}}</strong></div></div>
  <p v-if="error" class="error" role="alert">{{error}}</p><p v-if="notice" class="notice" role="status">{{notice}}</p>
  <div class="review-grid"><div class="panel queue"><div class="panel-head"><h2>学生作答</h2></div>
    <div class="filters"><button v-for="f in [['all','全部'],['pending','待复核'],['reviewed','已反馈']]" :key="f[0]" :class="{selected:filter===f[0]}" @click="changeFilter(f[0])" :disabled="busy">{{f[1]}}</button></div>
    <p class="empty" v-if="!visible.length">{{busy?'读取中…':'暂无此状态的作答。'}}</p>
    <button v-for="w in visible" :key="w.id" class="work" :class="{current:selected===w.id}" @click="select(w)" :disabled="busy">
      <span><b>{{w.name}}</b><small>{{labels[w.state]}}</small></span><span class="excerpt">{{w.answer}}</span><time>{{when(w.created)}}</time></button>
  </div>
  <article class="panel detail"><div v-if="!item" class="empty-state"><i class="paper-icon"></i><h2>等待学生作答</h2><p>同班学生在小程序交作业后，点击「刷新作业」即可查看。</p></div>
    <template v-else><div class="panel-head"><h2>{{item.name}}的作答</h2><span class="pill">{{labels[item.state]}}</span></div><p class="muted">{{question}}</p><blockquote>{{item.answer}}</blockquote>
    <template v-if="item.review"><h3>已发送的反馈</h3><p class="body-text">{{item.review.feedback}}</p><small>{{item.review.verdict==='correct'?'正确':'需订正'}}　{{item.review.tag}}</small></template>
    <form v-else-if="eligible(item)" @submit.prevent="publish"><div v-if="item.draft" class="draft"><small>{{item.draft.source}} · 批改草稿</small><p>{{item.draft.feedback}}</p></div>
      <p v-else class="muted">自动批改未完成，请根据原作答填写反馈。</p>
      <label>教师判断<select v-model="verdict" required><option disabled value="">请选择</option><option value="correct">正确</option><option value="incorrect">需订正</option></select></label>
      <label>反馈给学生<textarea v-model="feedback" maxlength="1000" required rows="3"/></label>
      <label v-if="verdict==='incorrect'">错因<input v-model="tag" maxlength="80" required></label>
      <button class="primary" :disabled="busy || !verdict || !feedback.trim() || (verdict==='incorrect' && !tag.trim())">确认并发送反馈</button></form>
    <p v-else class="muted">批改正在处理，稍后刷新查看草稿。</p></template>
  </article></div>
  <section class="panel summary"><h2>班级错因</h2><p class="muted" v-if="!summary.errors.length">教师确认需要订正的作答后，这里会按错因汇总。</p>
    <div v-for="row in summary.errors" :key="row.tag" class="sum-row"><span>{{row.tag}}</span><b>{{row.count}} 份</b></div></section>
</section></template>
