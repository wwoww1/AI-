import { api, dateText, leave, message, states, Submission, Summary } from '../../api'

type Item = Submission & { created: number }
Page({
  data: { items: [] as (Item & { status: string; date: string })[], summary: { reviewed: 0, errors: [] } as Summary, error: '', loading: true },
  onShow() { this.refresh() },
  async refresh() {
    try {
      const [items, summary] = await Promise.all([api<Item[]>('/submissions'), api<Summary>('/summary')])
      this.setData({ items: items.map(s => ({ ...s, status: states[s.state], date: dateText(s.created) })), summary, error: '' })
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ loading: false }); wx.stopPullDownRefresh() }
  },
  onPullDownRefresh() { this.refresh() },
  open(event: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: '/pages/review/index?id=' + event.currentTarget.dataset.id })
  },
  leave,
})
