<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, errorText, session, setSession, type Session } from './api'
import Reviews from './Reviews.vue'
import Lessons from './Lessons.vue'
import Homework from './Homework.vue'
import Chat from './Chat.vue'
import Check from './Check.vue'
import Focus from './Focus.vue'

const pages = {review:Reviews,lessons:Lessons,homework:Homework,chat:Chat,focus:Focus,preview:Check,check:Check}
type Tab = keyof typeof pages
const titles: Record<Tab,string> = {review:'作业复核',lessons:'备课与教案',homework:'我的作业',chat:'AI 老师',focus:'学习督导',preview:'预习检测',check:'复习检测'}
const teacher = computed(()=>session.value?.role==='teacher')
const menu = computed<Tab[]>(()=>teacher.value?['review','lessons']:['homework','chat','focus','preview','check'])
const tab = ref<Tab>(teacher.value?'review':'homework')
const demo = ref(false), key = ref(''), error = ref(''), busy = ref(false)
async function loadOptions() {
  try { demo.value = (await api<{demo:boolean}>('/login/options')).demo; error.value = '' }
  catch (e) { error.value = errorText(e) }
}
onMounted(loadOptions)
watch(session, value => { tab.value=value?.role==='teacher'?'review':'homework'; if (!value) {key.value='';loadOptions()} })
async function login(demoRole?: 'student'|'teacher') {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const user = demoRole ? await api<Session>('/login/demo',{role:demoRole}) : await api<Session>('/login/web',{access_key:key.value})
    setSession(user); key.value = ''
  } catch (e) { error.value = errorText(e) } finally { busy.value = false }
}
async function logout() {
  if (busy.value) return
  busy.value = true
  try { await api('/logout',{}); setSession(null) } catch (e) { error.value = errorText(e) }
  finally { busy.value = false }
}
</script>
<template>
  <div v-if="!session" class="login-layout">
    <section class="login-cover"><div class="brand"><i class="mark"></i>教学工作台</div>
      <div class="board"><p>异分母分数加法</p><div class="equation"><span>1<em>2</em></span> + <span>1<em>4</em></span> = <span>3<em>4</em></span></div><div class="fraction-strip"></div></div>
      <div class="cover-foot">自主学习　 /　 教学准备</div>
    </section>
    <main class="login-main"><form class="login-form" @submit.prevent="login()">
      <h1>登录工作台</h1><p class="muted">使用个人登录码进入你的学习或教学空间。</p>
      <label>个人登录码<input v-model.trim="key" type="password" required autocomplete="current-password" placeholder="输入管理员分配的登录码"></label>
      <button class="primary" :disabled="busy || !key">登录</button>
      <div v-if="demo" class="pair"><button class="secondary" type="button" :disabled="busy" @click="login('student')">学生演示</button><button class="secondary" type="button" :disabled="busy" @click="login('teacher')">教师演示</button></div>
      <p v-if="error" class="error" role="alert">{{error}} <button type="button" class="link" @click="loadOptions">重试连接</button></p>
    </form></main>
  </div>
  <div v-else class="shell"><aside class="rail"><div class="brand"><i class="mark"></i>教学工作台</div>
    <nav aria-label="工作台导航"><button v-for="page in menu" :key="page" :class="{active:tab===page}" @click="tab=page">{{titles[page]}}</button></nav>
    <footer><div class="user"><b>{{session.name.slice(-1)}}</b><span>{{session.name}}<small>{{teacher?'教师':'学生'}}</small></span></div><button class="exit" :disabled="busy" @click="logout">退出登录</button></footer>
  </aside><main class="desk"><div class="topline"><span>{{teacher?'教学':'学习'}}工作区</span><span>班级 · {{session.class_id}}</span></div>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <KeepAlive><component :is="pages[tab]" :key="tab" v-bind="tab==='preview'||tab==='check'?{stage:tab==='preview'?'preview':'review'}:{}"/></KeepAlive>
  </main></div>
</template>
