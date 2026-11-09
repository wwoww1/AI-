import { api, message, Role, Session } from '../../api'
import { DEMO_LOGIN } from '../../config'

Page({
  data: { demo: DEMO_LOGIN, busy: false, error: '' },
  async enter(event: WechatMiniprogram.TouchEvent) {
    if (this.data.busy) return
    this.setData({ busy: true, error: '' })
    try {
      let session: Session
      if (DEMO_LOGIN) {
        const role = event.currentTarget.dataset.role as Role
        session = await api<Session>('/login/demo', { role })
      } else {
        const code = await new Promise<string>((resolve, reject) =>
          wx.login({ success: res => resolve(res.code), fail: () => reject(new Error('微信登录失败，请重试')) }))
        session = await api<Session>('/login/wechat', { code })
      }
      wx.setStorageSync('session', session)
      wx.reLaunch({ url: '/pages/' + session.role + '/index' })
    } catch (err) { this.setData({ error: message(err) }) }
    finally { this.setData({ busy: false }) }
  },
})
