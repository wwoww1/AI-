# 小程序与网页独立上线

两端都包含学生和教师工作台。客户端各自发布，互相无需知道对方的网址。学生、班级、作业、问答、检测、学习目标和教师草稿均由共享 API 管理。已提交或已保存的数据在另一端重新进入对应页面或刷新后可见。

## 先部署共享 API

在包含 `backend/` 的目录安装 `backend/requirements.txt` 并启动 `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`。用域名和 HTTPS 反向代理对外提供 `/api`。沿用现有服务时，继续使用原 `DATABASE_PATH`；首次安装将它指向持久化磁盘。启动时会补建网页登录凭据表。实例应能读写数据库所在目录。

正式环境设置 `DEMO_MODE=0`，配置 `MEMBERS_FILE`、`WX_APP_ID`、`WX_APP_SECRET`。模型设置见 README。演示环境仅用于本机，启用后每个角色分别共享一个固定示例账号。

## 对齐两端身份

成员名单是服务端的私有 UTF-8 JSON 文件。已有微信成员保持原 OpenID 键、原班级和原有字段，即可继续读取原来的历史记录。例如：

```json
{
  "实际学生OpenID": {"role":"student","name":"学生甲","class_id":"class-a"},
  "实际教师OpenID": {"role":"teacher","name":"李老师","class_id":"class-a"}
}
```

网页使用个人登录码，小程序使用微信登录，两种登录方式均从同一条成员记录确定角色和班级。在部署 API 的环境中配置相同的 `DATABASE_PATH`、`MEMBERS_FILE` 后，分别运行：

```shell
python -m backend.web_account --member "实际学生OpenID"
python -m backend.web_account --member "实际教师OpenID"
```

每次命令会输出一个随机登录码，只交给对应成员；后端保存其摘要。再次对同一成员执行命令会轮换登录码并撤销已有会话。网页输入登录码后会自动进入所属角色。应用和网页都无需内置成员名单或密钥。

**网页先上线时**，可从第一天就在新成员记录中设置唯一的固定 `account_id`，例如 `"account_id":"student-001"`，暂用 `student-001` 作为名单的键。待小程序接入时把键改成实际 OpenID，保留原 `account_id` 和班级。网页登录码及历史记录仍然有效。对已经产生数据且没有 `account_id` 的旧微信成员，继续使用原 OpenID 作为身份依据；新增或变更 `account_id` 会指向另一份身份记录。

## 单独发布微信小程序

1. 解压 `发布包/微信小程序.zip`，或直接在开发者工具导入源码目录 `wechat/`。
2. 在 `project.config.json` 填写实际小程序 AppID。在 `miniprogram/config.ts` 将 `API_BASE` 改为正式 HTTPS API 的完整地址（含 `/api`），并将 `DEMO_LOGIN` 设为 `false`。
3. 在微信公众平台登记 API 的 request 合法域名，在开发者工具预览、真机验证并上传审核。微信登录根据成员身份显示学生或教师工作台。

## 单独发布网页

1. 解压 `发布包/网页静态站.zip`。也可自行在 `web/` 运行 `pnpm install --frozen-lockfile` 和 `pnpm build`，得到 `dist/`。
2. 选择下面一种连接方式，上传包含 `index.html`、`config.js` 和 `assets/` 的全部内容。使用 HTTP(S) 托管访问。
   - **同域代理**：保留 `config.js` 的 `/api`，让网页域名将 `/api/*` 原路径代理到后端，同时转发 Authorization 请求头。
   - **不同域名**：编辑发布目录的 `config.js`，例如 `window.TEACHING_API_BASE = 'https://api.example.cn/api';`。后端设置 `WEB_ORIGINS=https://learn.example.cn` 后重启。多个网页来源用逗号分隔，值为协议、域名和可选端口。
3. 打开网页，分别用个人登录码验证两种身份。更换 API 域名时，网页可直接更新已部署的 `config.js`。建议对该文件和 `index.html` 使用重新验证缓存，避免配置更新后仍访问旧地址。

## 联调验收

同班学生在小程序提交作答；教师从网页进入「作业复核」，刷新、核对并发送反馈。学生从任一端刷新提交记录即可查看反馈。用同一位教师的网页账号生成并保存一份教案，再从小程序「我的备课」打开。同一账号、同一班级、同一后端数据库是数据互通的条件。

后续更新客户端时，先重新构建网页，再从项目根目录运行 `python tools/package_release.py` 即可更新两个发布包。
