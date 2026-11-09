import { api, message, requestId } from '../../api'

interface LessonRef { id: number; topic: string; has_plan: boolean }
interface Lesson { id: number; topic: string; audience: string; goal: string; minutes: number; prep: string; plan: string;
  prep_source: string; plan_source: string; revision: number; errors: { tag: string; count: number }[] }

Page({
  data: { lessons: [] as LessonRef[], current: null as Lesson|null, topic: '', audience: '', goal: '', minutes: '40',
    includeErrors: false, prep: '', plan: '', key: '', busy: false, dirty: false, error: '' },
  onLoad() { this.list() },
  async list() {
    try { this.setData({ lessons: await api<LessonRef[]>('/lessons') }) }
    catch (err) { this.setData({ error: message(err) }) }
  },
  show(lesson: Lesson) {
    this.setData({ current: lesson, prep: lesson.prep, plan: lesson.plan, dirty: false })
    wx.pageScrollTo({ scrollTop: 0, duration: 0 })
  },
  async open(event: WechatMiniprogram.TouchEvent) {
    if (this.data.busy) return
    this.setData({ busy: true, error: '' })
    try { this.show(await api<Lesson>('/lessons/' + event.currentTarget.dataset.id)) }
    catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
  edit(event: WechatMiniprogram.Input) {
    const field = event.currentTarget.dataset.field as string
    this.setData({ [field]: event.detail.value, key: '', dirty: !!this.data.current })
  },
  toggle(event: WechatMiniprogram.SwitchChange) { this.setData({ includeErrors: event.detail.value, key: '' }) },
  async create() {
    if (this.data.busy) return
    const { topic, audience, goal, includeErrors } = this.data
    const minutes = Number(this.data.minutes)
    if (!topic.trim() || !audience.trim() || !goal.trim() || !Number.isInteger(minutes) || minutes < 5 || minutes > 180) {
      this.setData({ error: '请填写课题、授课对象、目标及 5 到 180 分钟的课时。' }); return
    }
    const key = this.data.key || requestId()
    this.setData({ key, busy: true, error: '' })
    try {
      this.show(await api<Lesson>('/lessons', { topic, audience, goal, minutes, include_errors: includeErrors, request_id: key }))
      this.setData({ topic: '', goal: '', key: '' })
      await this.list()
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
  async update(event: WechatMiniprogram.TouchEvent) {
    const { current, prep, plan, busy } = this.data
    if (!current || busy) return
    if (!prep.trim() || (current.plan && !plan.trim())) {
      this.setData({ error: '请保留备课内容及已生成的教案正文。' }); return
    }
    const action = event.currentTarget.dataset.action === 'plan' ? 'plan' : 'save'
    this.setData({ busy: true, error: '' })
    try {
      this.show(await api<Lesson>('/lessons/' + current.id + '/' + action,
        { revision: current.revision, prep, ...(action === 'save' ? { plan } : {}) }))
      await this.list()
      wx.showToast({ title: action === 'plan' ? '教案已生成' : '修改已保存' })
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
  back() {
    if (this.data.busy) return
    const close = () => { this.setData({ current: null, dirty: false, error: '' }); this.list() }
    if (this.data.dirty) wx.showModal({ title: '离开编辑？', content: '本次未保存的修改将丢失。', confirmText: '离开', success: r => { if (r.confirm) close() } })
    else close()
  },
})
