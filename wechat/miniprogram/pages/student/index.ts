import { api, Assignment, leave, message, states, dateText, Submission, requestId } from '../../api'

type Item = Submission & { created: number }
Page({
  data: { task: null as Assignment | null, answer: '', requestId: '', sending: false, error: '',
    history: [] as (Item & { status: string; date: string })[], loading: true },
  onShow() { this.refresh() },
  async refresh() {
    try {
      const [task, items] = await Promise.all([api<Assignment>('/assignment'), api<Item[]>('/submissions')])
      this.setData({ task, history: items.map(s => ({ ...s, status: states[s.state], date: dateText(s.created) })), error: '' })
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ loading: false }); wx.stopPullDownRefresh() }
  },
  onPullDownRefresh() { this.refresh() },
  edit(event: WechatMiniprogram.Input) {
    this.setData({ answer: event.detail.value, requestId: '' })
  },
  async submit() {
    if (this.data.sending || !this.data.answer.trim()) return
    const key = this.data.requestId || requestId()
    this.setData({ sending: true, requestId: key, error: '' })
    try {
      await api('/submissions', { answer: this.data.answer.trim(), request_id: key })
      this.setData({ answer: '', requestId: '' })
      wx.showToast({ title: '作业已提交', icon: 'success' })
      await this.refresh()
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ sending: false }) }
  },
  leave,
})
