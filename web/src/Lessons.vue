<script setup lang="ts">
import { computed,onActivated,reactive,ref } from 'vue'
import { api,type Lesson,type LessonRef } from './api'
import { retryKey,useAction } from './actions'
const items=ref<LessonRef[]>([]),current=ref<Lesson|null>(null), prep=ref(''), plan=ref('')
const brief=reactive({topic:'',audience:'',goal:'',minutes:40,include_errors:false})
const dirty=computed(()=>current.value && (prep.value!==current.value.prep||plan.value!==current.value.plan))
const {busy,error,run}=useAction(), key=retryKey(), notice=ref('')
async function list(){items.value=await api<LessonRef[]>('/lessons')}
onActivated(()=>run(list))
function display(l:Lesson){current.value=l;prep.value=l.prep;plan.value=l.plan}
function mayLeave(){return !dirty.value||window.confirm('离开编辑并放弃未保存的修改？')}
function open(id:number){if(!mayLeave())return;run(async()=>{display(await api<Lesson>('/lessons/'+id));notice.value=''})}
function create(){run(async()=>{
  display(await api<Lesson>('/lessons',{...brief,request_id:key.for(brief)}));key.clear();brief.topic='';brief.goal='';notice.value='备课已保存。';await list()
})}
function update(action:'save'|'plan'){run(async()=>{
  const l=current.value;if(!l)return
  display(await api<Lesson>('/lessons/'+l.id+'/'+action,{prep:prep.value,revision:l.revision,...(action==='save'?{plan:plan.value}:{})}))
  notice.value=action==='save'?'修改已保存。':'教案已生成。';await list()
})}
function fresh(){if(mayLeave()){current.value=null;notice.value=''}}
</script>
<template><section><header class="page-head"><div><h1>备课与教案</h1><p class="muted">准备课堂内容，用当前备课生成教案。</p></div><button class="secondary" :disabled="busy" @click="fresh">新建备课</button></header>
<p v-if="error" role="alert" class="error">{{error}}</p><p v-if="notice" role="status" class="notice">{{notice}}</p>
<div class="review-grid"><aside class="panel queue"><div class="panel-head"><h2>我的备课</h2><button class="link" @click="run(list)" :disabled="busy">刷新</button></div><p v-if="!items.length" class="empty">暂无已保存的备课。</p><button v-for="l in items" :key="l.id" class="work" :class="{current:current?.id===l.id}" :disabled="busy" @click="open(l.id)"><b>{{l.topic}}</b><small>{{l.has_plan?'已有教案':'备课草稿'}}</small></button></aside>
<article class="panel"><form v-if="!current" @submit.prevent="create"><h2>新建备课</h2><fieldset :disabled="busy"><label>课题<input v-model.trim="brief.topic" maxlength="120" placeholder="例如：异分母分数加法" required></label><div class="pair"><label>授课对象<input v-model.trim="brief.audience" maxlength="80" required></label><label>课时（分钟）<input v-model.number="brief.minutes" type="number" min="5" max="180" required></label></div><label>教学目标与设想<textarea v-model.trim="brief.goal" rows="4" maxlength="800" required/></label><label class="option"><input v-model="brief.include_errors" type="checkbox">参考本班已确认错因</label><button class="primary">生成备课建议</button></fieldset></form>
<template v-else><small>{{current.audience}} · {{current.minutes}} 分钟</small><h2>{{current.topic}}</h2><p>{{current.goal}}</p><div v-if="current.errors.length" class="draft"><small>本班已确认错因</small><p v-for="row in current.errors" :key="row.tag">{{row.tag}} · {{row.count}} 份</p></div>
<label>备课建议 · {{current.prep_source}}<textarea v-model="prep" rows="12" maxlength="10000" :disabled="busy"/></label>
<label v-if="current.plan">教案草稿 · {{current.plan_source}}<textarea v-model="plan" rows="16" maxlength="10000" :disabled="busy"/></label>
<div class="pair"><button v-if="!current.plan" class="primary" :disabled="busy||!prep.trim()" @click="update('plan')">用当前备课生成教案</button><button class="secondary" :disabled="busy||!dirty||!prep.trim()||(!!current.plan&&!plan.trim())" @click="update('save')">保存修改</button></div></template></article></div></section></template>
