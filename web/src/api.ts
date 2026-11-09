import { ref } from 'vue'

export interface Session { token: string; role: string; name: string; class_id: string }
declare global { interface Window { TEACHING_API_BASE?: string } }
function restored(): Session | null {
  try {
    const data = JSON.parse(sessionStorage.getItem('teaching-session') || 'null')
    return ['student','teacher'].includes(data?.role) && typeof data?.token === 'string' ? data : null
  } catch { return null }
}
export const session = ref<Session | null>(restored())
export function setSession(value: Session | null) {
  if (value) sessionStorage.setItem('teaching-session', JSON.stringify(value))
  else sessionStorage.removeItem('teaching-session')
  session.value = value
}
export async function api<T>(path: string, payload?: object): Promise<T> {
  const base = (window.TEACHING_API_BASE || '/api').replace(/\/$/, '')
  const headers: Record<string,string> = {}
  const token = session.value?.token
  if (payload) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = 'Bearer ' + token
  let response: Response
  try {
    response = await fetch(base + path, { method: payload ? 'POST' : 'GET', headers,
      body: payload ? JSON.stringify(payload) : undefined, cache: 'no-store' })
  } catch { throw Error('无法连接教学服务，请检查网络或 API 地址。') }
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail
    if (response.status === 401 && token && token === session.value?.token) setSession(null)
    throw Error(typeof detail === 'string' ? detail : '请求失败，请检查输入或稍后重试。')
  }
  if (!response.headers.get('content-type')?.includes('application/json')) throw Error('请检查 API 地址或网页反向代理配置。')
  return response.json()
}
export const errorText = (e: unknown) => e instanceof Error ? e.message : '请求失败，请重试。'
export interface Assessment { verdict: 'correct'|'incorrect'|'uncertain'; feedback: string; tag: string; source?: string }
export interface Work { id: number; name: string; answer: string; state: string; draft?: Assessment|null; review?: Assessment|null; created: number }
export interface Summary { reviewed: number; errors: {tag:string;count:number}[] }
export interface LessonRef { id: number; topic: string; has_plan: boolean }
export interface Lesson { id: number; topic: string; audience: string; goal: string; minutes: number; prep: string; plan: string; revision:number; errors: Summary['errors']; prep_source:string; plan_source:string }
