import { API_BASE } from './config'

export type Role = 'student' | 'teacher'
export interface Session { token: string; role: Role; name: string }
export interface Assignment { id: string; title: string; prompt: string }
export type Verdict = 'correct' | 'incorrect' | 'uncertain'
export interface Assessment { verdict: Verdict; feedback: string; tag: string; source?: string }
export interface Submission { id: number; name: string; answer: string; state: string; draft?: Assessment; review?: Assessment }
export interface Summary { reviewed: number; errors: { tag: string; count: number }[] }

export function api<T>(path: string, body?: object): Promise<T> {
  const token = wx.getStorageSync('session')?.token
  return new Promise((resolve, reject) => wx.request({
    url: API_BASE + path,
    method: body === undefined ? 'GET' : 'POST',
    data: body ? JSON.stringify(body) : undefined,
    header: { 'content-type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    success(res) {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        resolve(res.data as T)
        return
      }
      if (res.statusCode === 401 && !path.startsWith('/login/')) {
        leave()
      }
      const detail = (res.data as { detail?: unknown })?.detail
      reject(new Error(typeof detail === 'string' ? detail : '请求失败，请检查输入后重试'))
    },
    fail: () => reject(new Error('未能连接服务，请确认后端地址并重试')),
  }))
}
export function message(err: unknown) { return err instanceof Error ? err.message : '操作失败，请重试' }
export function requestId() { return Date.now() + '-' + Math.random().toString(36).slice(2) }
export function leave() {
  wx.removeStorageSync('session')
  wx.reLaunch({ url: '/pages/login/index' })
}
export const states: Record<string, string> = {
  submitted: '已提交，等待教师反馈', queued: '等待批改', grading: '批改中',
  draft: '待复核', failed: '需人工批改', reviewed: '已反馈',
}
export function dateText(seconds: number) {
  const d = new Date(seconds * 1000)
  const pad = (n: number) => ('0' + n).slice(-2)
  return (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}
