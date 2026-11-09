import { api, message, requestId } from '../../api'

interface Turn { id: number; question: string; answer: string; source: string }

Page({
  data: { turns: [] as Turn[], question: '', key: '', error: '', busy: false, ready: false },
  onLoad() { this.load() },
  async load() {
    try {
      const turns = await api<Turn[]>('/study/chat')
      this.setData({ turns, ready: true })
    } catch (err) { this.setData({ ready: false, error: message(err) }) }
  },
  edit(event: WechatMiniprogram.Input) { this.setData({ question: event.detail.value, key: '' }) },
  async send() {
    const question = this.data.question.trim()
    if (!this.data.ready || this.data.busy || !question) return
    const key = this.data.key || requestId()
    const turns = this.data.turns
    this.setData({ busy: true, key, error: '' })
    try {
      const turn = await api<Turn>('/study/chat', { question, request_id: key, after: turns.length ? turns[turns.length-1].id : 0 })
      this.setData({ turns: [...turns.filter(t => t.id !== turn.id), turn].slice(-50), question: '', key: '' })
    } catch (err) {
      this.setData({ error: message(err) })
      await this.load()
    } finally { this.setData({ busy: false }) }
  },
})
