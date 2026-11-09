<script setup lang="ts">
import { onActivated,ref } from 'vue'
import { api } from './api'
import { retryKey,useAction } from './actions'
interface Turn {id:number; question:string; answer:string; source:string}
const turns=ref<Turn[]>([]), question=ref(''), ready=ref(false), key=retryKey()
const {busy,error,run}=useAction()
async function load(){turns.value=await api<Turn[]>('/study/chat');ready.value=true}
onActivated(()=>run(load))
function send(){run(async()=>{
  const text=question.value.trim();if(!text)return
  const id=key.for({text})
  try{await api('/study/chat',{request_id:id,question:text,after:turns.value.at(-1)?.id||0});question.value='';key.clear()}
  finally{await load()}
})}
</script>
<template><section><header class="page-head"><div><h1>AI 老师</h1><p class="muted">写下卡住的那一步，或接着上一条回答继续问。</p></div><button class="secondary" :disabled="busy" @click="run(load)">刷新对话</button></header>
<p v-if="error" class="error">{{error}}</p><div class="panel"><p v-if="!turns.length" class="empty">试试问「为什么分数相加要先通分？」</p><article v-for="t in turns" :key="t.id" class="entry"><small>我的提问</small><p class="body-text">{{t.question}}</p><div class="draft"><small>{{t.source}}</small><p class="body-text">{{t.answer}}</p></div></article>
<form @submit.prevent="send"><label>提问<textarea v-model="question" maxlength="2000" rows="3" :disabled="busy" required/></label><button class="primary" :disabled="busy || !ready || !question.trim()">{{busy?'请稍候…':'发送问题'}}</button></form></div></section></template>
