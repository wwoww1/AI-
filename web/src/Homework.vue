<script setup lang="ts">
import { onActivated,ref } from 'vue'
import { api,type Work } from './api'
import { dateTime,retryKey,useAction } from './actions'
const {busy,error,run}=useAction(), key=retryKey()
const task=ref<{title:string;prompt:string}>(), items=ref<Work[]>([]), answer=ref(''), notice=ref('')
async function load(){ [task.value,items.value]=await Promise.all([api<{title:string;prompt:string}>('/assignment'),api<Work[]>('/submissions')]) }
onActivated(()=>run(load))
function submit(){run(async()=>{
  const data={answer:answer.value.trim()};if(!data.answer)return
  await api('/submissions',{...data,request_id:key.for(data)});key.clear();answer.value='';notice.value='作业已提交。';await load()
})}
</script>
<template><section><header class="page-head"><div><h1>我的作业</h1><p class="muted">提交作答，查看教师反馈。</p></div><button class="secondary" @click="run(load)" :disabled="busy">刷新记录</button></header>
<p class="error" v-if="error" role="alert">{{error}}</p><p class="notice" v-if="notice">{{notice}}</p>
<div class="review-grid student-grid"><form v-if="task" class="panel" @submit.prevent="submit"><h2>{{task.title}}</h2><p>{{task.prompt}}</p><label>我的作答<textarea v-model="answer" required maxlength="2000" rows="6" placeholder="写下计算过程和答案"/></label><button class="primary" :disabled="busy || !answer.trim()">提交作业</button></form>
<section class="panel"><h2>提交记录</h2><p class="empty" v-if="!items.length">还没有提交记录。</p><article class="entry" v-for="w in items" :key="w.id"><small>{{dateTime(w.created)}} · {{w.review?'已反馈':'等待教师反馈'}}</small><p class="body-text">{{w.answer}}</p><div v-if="w.review" class="draft"><b>{{w.review.verdict==='correct'?'正确':'需订正'}}</b><p>{{w.review.feedback}}</p><small v-if="w.review.tag">{{w.review.tag}}</small></div></article></section></div></section></template>
