import { api, message, requestId } from '../../api'

interface Focus { id: number; state: 'running'|'paused'|'done'; remaining: number; minutes: number; goal: string }
interface Advice { text: string; source: string }

function clock(seconds: number) { return Math.floor(seconds / 60) + ':' + ('0' + seconds % 60).slice(-2) }

Page({
  data: { focus: null as Focus | null, goal: '', minutes: '15', key: '', busy: false, loading: true, error: '',
    timeText: '', advice: null as Advice | null, advising: false },
  visible: false,
  alerted: 0,
  timer: undefined as ReturnType<typeof setInterval> | undefined,
  stopTimer() {
    if (this.timer !== undefined) clearInterval(this.timer)
    this.timer = undefined
  },
  onShow() { this.visible = true; this.load() },
  onHide() { this.visible = false; this.stopTimer() },
  onUnload() { this.visible = false; this.stopTimer() },
  display(focus: Focus | null) {
    this.stopTimer()
    if (this.data.focus?.id !== focus?.id) this.setData({ advice: null })
    this.setData({ focus, timeText: focus ? clock(focus.remaining) : '', loading: false })
    if (!focus || focus.state !== 'running' || !this.visible) return
    const deadline = Date.now() + focus.remaining * 1000
    const tick = () => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
      this.setData({ timeText: clock(left) })
      if (left === 0) {
        this.stopTimer()
        if (this.alerted !== focus.id) {
          this.alerted = focus.id
          wx.showToast({ title: '约定时间到了，检查一下学习目标吧', icon: 'none' })
        }
      }
    }
    if (focus.remaining > 0) this.timer = setInterval(tick, 1000)
    tick()
  },
  async load() {
    try { this.display(await api<Focus|null>('/study/focus')); this.setData({ error: '' }) }
    catch (err) { this.setData({ loading: false, error: message(err) }) }
  },
  goalInput(event: WechatMiniprogram.Input) { this.setData({ goal: event.detail.value, key: '' }) },
  timeInput(event: WechatMiniprogram.Input) { this.setData({ minutes: event.detail.value, key: '' }) },
  async start() {
    if (this.data.busy) return
    const goal = this.data.goal.trim(), minutes = Number(this.data.minutes)
    if (!goal || !Number.isInteger(minutes) || minutes < 1 || minutes > 120) {
      this.setData({ error: '请填写目标，并输入 1 到 120 之间的整数分钟。' }); return
    }
    const key = this.data.key || requestId()
    this.setData({ key, busy: true, error: '' })
    try {
      this.display(await api<Focus>('/study/focus', { goal, minutes, request_id: key }))
      this.setData({ key: '', goal: '', advice: null })
    } catch (err) { await this.load(); this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
  async change(event: WechatMiniprogram.TouchEvent) {
    const focus = this.data.focus
    if (!focus || this.data.busy) return
    this.setData({ busy: true, error: '' })
    try {
      this.display(await api<Focus>('/study/focus/' + focus.id + '/state', { state: event.currentTarget.dataset.state, expected: focus.state }))
      this.setData({ advice: null })
    } catch (err) { await this.load(); this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
  async coach() {
    const focus = this.data.focus
    if (!focus || this.data.advising) return
    this.setData({ advising: true, error: '' })
    try {
      const advice = await api<Advice>('/study/focus/' + focus.id + '/advice', {})
      if (this.data.focus?.id === focus.id && this.data.focus.state === focus.state) this.setData({ advice })
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ advising: false }) }
  },
})
