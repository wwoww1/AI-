import { api, dateText, message, requestId } from '../../api'

type Stage = 'preview' | 'review'
interface Question { id: string; prompt: string; skill: string; options: string[] }
interface Detail { id: string; prompt: string; skill: string; chosen: string; expected: string; ok: boolean; reason: string }
interface Result { id: number; created: number; score: number; total: number; items: Detail[] }
interface Sheet { topic: string; questions: Question[]; history: Result[] }

Page({
  data: { stage: 'preview' as Stage, title: '', sheet: null as Sheet | null, answers: {} as Record<string, number>,
    history: [] as (Result & { date: string })[], result: null as Result | null, key: '', busy: false, error: '' },
  onLoad(options) {
    const stage = options.stage === 'review' ? 'review' : 'preview'
    const title = stage === 'preview' ? '预习检测' : '复习检测'
    this.setData({ stage, title })
    wx.setNavigationBarTitle({ title })
    this.load()
  },
  async load() {
    try {
      const sheet = await api<Sheet>('/study/checks/' + this.data.stage)
      this.setData({ sheet, history: sheet.history.map(r => ({ ...r, date: dateText(r.created) })), error: '' })
    } catch (err) { this.setData({ error: message(err) }) }
  },
  choose(event: WechatMiniprogram.RadioGroupChange) {
    const id = event.currentTarget.dataset.id as string
    this.setData({ answers: { ...this.data.answers, [id]: Number(event.detail.value) }, key: '' })
  },
  async submit() {
    const { sheet, answers, busy, stage } = this.data
    if (!sheet || busy) return
    if (sheet.questions.some(q => answers[q.id] === undefined)) {
      this.setData({ error: '每道题都需要选择一个答案。' })
      return
    }
    const key = this.data.key || requestId()
    this.setData({ key, busy: true, error: '' })
    try {
      const result = await api<Result>('/study/checks/' + stage, { answers, request_id: key })
      this.setData({ result, answers: {}, key: '' })
      await this.load()
      wx.pageScrollTo({ scrollTop: 0, duration: 0 })
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
  again() { this.setData({ result: null, answers: {}, key: '', error: '' }) },
  inspect(event: WechatMiniprogram.TouchEvent) {
    const result = this.data.history.find(r => r.id === event.currentTarget.dataset.id)
    if (result) { this.setData({ result }); wx.pageScrollTo({ scrollTop: 0, duration: 0 }) }
  },
})
