import { api, Assignment, message, Submission } from '../../api'

Page({
  data: { task: null as Assignment | null, item: null as Submission | null, verdict: '', feedback: '', tag: '', error: '', busy: false },
  async onLoad(options) {
    try {
      const [items, task] = await Promise.all([api<Submission[]>('/submissions'), api<Assignment>('/assignment')])
      const item = items.find(row => row.id === Number(options.id))
      if (!item || !['draft', 'failed'].includes(item.state)) throw new Error('这份作业不能复核，请返回列表刷新')
      const draft = item.draft
      this.setData({ item, task, feedback: draft?.feedback || '', tag: draft?.tag || '',
        verdict: draft && draft.verdict !== 'uncertain' ? draft.verdict : '' })
    } catch (err) { this.setData({ error: message(err) }) }
  },
  select(event: WechatMiniprogram.RadioGroupChange) { this.setData({ verdict: event.detail.value }) },
  feedbackInput(event: WechatMiniprogram.Input) { this.setData({ feedback: event.detail.value }) },
  tagInput(event: WechatMiniprogram.Input) { this.setData({ tag: event.detail.value }) },
  async save() {
    const { item, verdict, feedback, tag, busy } = this.data
    if (!item || busy) return
    if (!verdict || !feedback.trim() || (verdict === 'incorrect' && !tag.trim())) {
      this.setData({ error: '请选择判断，填写反馈，并为错误作答注明错因。' })
      return
    }
    this.setData({ busy: true, error: '' })
    try {
      await api('/submissions/' + item.id + '/review', { verdict, feedback, tag })
      wx.navigateBack()
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
})
