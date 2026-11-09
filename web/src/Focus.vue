<script setup lang="ts">
import { computed,onActivated,onDeactivated,onBeforeUnmount,ref } from 'vue'
import { api } from './api'
import { useAction,retryKey } from './actions'
interface Focus {id:number; state:'running'|'paused'|'done'; remaining:number; minutes:number;goal:string}
const focus=ref<Focus|null>(null), goal=ref(''), minutes=ref(15), left=ref(0), advice=ref<{text:string;source:string}|null>(null)
const {busy,error,run}=useAction(), key=retryKey()
const time=computed(()=>Math.floor(left.value/60)+':'+String(left.value%60).padStart(2,'0'))
let timer:number|undefined, deadline=0
function display(f:Focus|null){if(f?.id!==focus.value?.id||f?.state!==focus.value?.state)advice.value=null;focus.value=f;left.value=f?.remaining||0;deadline=Date.now()+left.value*1000}
async function load(){display(await api<Focus|null>('/study/focus'))}
function sync(){if(document.visibilityState==='visible')run(load)}
function stop(){window.clearInterval(timer);document.removeEventListener('visibilitychange',sync)}
onActivated(()=>{run(load);timer=window.setInterval(()=>{if(focus.value?.state==='running')left.value=Math.max(0,Math.ceil((deadline-Date.now())/1000))},500);document.addEventListener('visibilitychange',sync)})
onDeactivated(stop);onBeforeUnmount(stop)
function start(){run(async()=>{const data={goal:goal.value.trim(),minutes:minutes.value};display(await api<Focus>('/study/focus',{...data,request_id:key.for(data)}));goal.value='';key.clear()})}
function change(state:string){run(async()=>{const f=focus.value;if(!f)return;try{display(await api<Focus>('/study/focus/'+f.id+'/state',{state,expected:f.state}))}catch(e){await load();throw e}})}
function coach(){run(async()=>{advice.value=await api('/study/focus/'+focus.value?.id+'/advice',{})})}
</script>
<template><section><header class="page-head"><div><h1>学习督导</h1><p class="muted">为一个目标留出时间，回到本页即可查看进度。</p></div><button class="secondary" @click="run(load)" :disabled="busy">刷新状态</button></header>
<p v-if="error" class="error">{{error}}</p><article v-if="focus" class="panel focus"><small>{{focus.state==='running'?'学习中':focus.state==='paused'?'已暂停':'已结束'}}</small><h2>{{focus.goal}}</h2><template v-if="focus.state!=='done'"><strong class="clock">{{time}}</strong><p v-if="left===0" role="status">约定时间到了，检查一下学习目标吧。</p><div class="pair"><button class="secondary" @click="change(focus.state==='running'?'paused':'running')" :disabled="busy">{{focus.state==='running'?'暂停':'继续'}}</button><button class="primary" @click="change('done')" :disabled="busy">结束本次学习</button></div></template><button class="link" @click="coach" :disabled="busy">获取督学建议</button><div v-if="advice" class="draft"><small>{{advice.source}}</small><p>{{advice.text}}</p></div></article>
<form v-if="!focus||focus.state==='done'" class="panel" @submit.prevent="start"><h2>新学习目标</h2><label>学习目标<input v-model="goal" required maxlength="160" placeholder="例如：独立完成一道通分题"></label><label>学习时长（分钟）<input v-model.number="minutes" type="number" min="1" max="120" required></label><button class="primary" :disabled="busy || !goal.trim()">开始学习</button></form></section></template>
