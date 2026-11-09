<script setup lang="ts">
import { computed,onActivated,ref } from 'vue'
import { api } from './api'
import { useAction,retryKey,dateTime } from './actions'
const props=defineProps<{stage:'preview'|'review'}>()
interface Report {id:number;created:number;score:number;total:number;items:{id:string;prompt:string;skill:string;chosen:string;expected:string;ok:boolean;reason:string}[]}
interface Sheet {topic:string;questions:{id:string;prompt:string;options:string[]}[];history:Report[]}
const sheet=ref<Sheet>(), result=ref<Report|null>(null), answers=ref<Record<string,number>>({})
const title=computed(()=>props.stage==='preview'?'预习检测':'复习检测')
const path=computed(()=>'/study/checks/'+props.stage)
const {busy,error,run}=useAction(), key=retryKey()
async function load(){sheet.value=await api<Sheet>(path.value)}
onActivated(()=>run(load))
function submit(){run(async()=>{
  const payload={answers:answers.value}
  result.value=await api<Report>(path.value,{...payload,request_id:key.for(payload)});key.clear();answers.value={};await load()
})}
</script>
<template><section><header class="page-head"><div><h1>{{title}}</h1><p class="muted">{{sheet?.topic}} · {{stage==='preview'?'检查概念理解':'检查计算与运用'}}</p></div><button class="secondary" @click="run(load)" :disabled="busy">刷新</button></header>
<p v-if="error" class="error">{{error}}</p><div class="review-grid student-grid"><div class="panel">
<template v-if="result"><h2>答对 {{result.score}} / {{result.total}} 题</h2><article class="entry" v-for="i in result.items" :key="i.id"><small>{{i.ok?'已答对':'再练一练'}} · {{i.skill}}</small><h3>{{i.prompt}}</h3><p>你的选择：{{i.chosen}}</p><p v-if="!i.ok">参考答案：{{i.expected}}</p><p class="draft">{{i.reason}}</p></article><button class="secondary" @click="result=null;answers={}">再做一次</button></template>
<form v-else-if="sheet" @submit.prevent="submit"><fieldset v-for="(q,n) in sheet.questions" :key="q.id"><legend>{{n+1}}. {{q.prompt}}</legend><label v-for="(opt,k) in q.options" :key="opt" class="option"><input v-model="answers[q.id]" type="radio" :name="q.id" :value="k" required :disabled="busy">{{opt}}</label></fieldset><button class="primary" :disabled="busy">提交检测</button></form></div>
<aside class="panel"><h2>历次结果</h2><p v-if="!sheet?.history.length" class="empty">完成检测后可回看逐题讲解。</p><button v-for="r in sheet?.history" :key="r.id" class="work" @click="result=r"><span>{{dateTime(r.created)}}<b>{{r.score}} / {{r.total}}</b></span></button></aside></div></section></template>
