# Croni Call：从空白 VPS 部署远程 MCP

本页对应 `croni/remote-mcp` 分支。目标是让电话引擎运行在 VPS，ChatGPT/Codex 只通过 HTTPS MCP 调用它。手机上的 Linphone 继续负责接听。

## 你需要准备

- 一台 x86_64 Linux VPS（Ubuntu 22.04/24.04，建议至少 2 核、2 GB 内存）
- 一个指向 VPS 的域名，例如 `call.example.com`
- 两个 Linphone SIP 账号：AI 账号用于拨号，手机账号用于接听
- 一个语音识别 key
- 手机上的 Linphone 已登录手机账号，并成功在前台接听过一次

SIP 密码、语音识别 key 和 MCP token 只写入 VPS 的私有环境文件，不要发到聊天、Issue 或提交记录。

## 1. 获取代码

```bash
git clone --branch croni/remote-mcp https://github.com/xuheloise-sketch/croni-call.git
cd croni-call
```

## 2. 安装电话引擎

先检查系统依赖，再运行上游提供的 Linux 安装器：

```bash
plugin-native/bin/install.sh --check
plugin-native/bin/install.sh \
  --pjsua2 https://github.com/yanyan1115/ringringring/releases/download/v0.1.0/pjsua2-2.17-linux-x86_64-cp311.tar.gz \
  --src .
```

随后创建独立 Python 环境：

```bash
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-remote.txt
```

如果安装器把 pjproject 放在其他位置，在环境文件中额外设置 `PJPROJECT_DIR`。

## 3. 写入私密配置

```bash
mkdir -p ~/.config/croni-call
cp .env.remote.example ~/.config/croni-call/remote.env
chmod 600 ~/.config/croni-call/remote.env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

编辑 `~/.config/croni-call/remote.env`：

- `VOICE_SIP_ID / USER / PASS` 填 AI 侧账号
- `VOICE_SIP_CALLEE` 填手机侧 SIP 地址
- `VOICE_STT_KEY` 填语音识别 key
- 三个 URL/host 字段换成你的域名
- 把刚生成的随机字符串填入 `CRONI_MCP_BEARER_TOKEN`
- 按需要调整静默时段、每日次数和最长通话时间

## 4. 先在本机回环测试

```bash
CRONI_ENV_FILE=$HOME/.config/croni-call/remote.env .venv/bin/python run_remote_mcp.py
```

另开一个 SSH 窗口：

```bash
curl -i http://127.0.0.1:8765/healthz
curl -i -X POST http://127.0.0.1:8765/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

第一条应返回 `{"status":"ok"}`；第二条没有 token，应返回 401。此时先不要真实拨号。

## 5. 用 systemd 常驻

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/croni-call.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now croni-call
systemctl --user status croni-call
loginctl enable-linger "$USER"
```

查看脱敏后的服务日志：

```bash
journalctl --user -u croni-call -f
```

## 6. 配置 HTTPS

把域名 A/AAAA 记录指向 VPS，然后安装 Caddy。复制示例并替换域名：

```bash
sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo systemctl reload caddy
curl -i https://call.example.com/healthz
```

MCP 服务只监听 `127.0.0.1:8765`，外部只接触 Caddy 的 443 端口。不要把 8765 直接暴露到公网。

## 7. 接入 ChatGPT/Codex

服务器地址是 `https://你的域名/mcp`，传输方式选择 Streamable HTTP，鉴权使用环境文件中的 Bearer token。

当前分支提供的是单用户静态 Bearer 启动方案。若你的 ChatGPT 插件创建界面只提供完整 OAuth，而没有直接填写 Bearer token 的选项，请停在这里：不要改成“无鉴权”，下一阶段应接入独立 OAuth 授权服务或 Secure MCP Tunnel。

首次接入后先运行只读的 `call_status`。确认成功，再手动授权一次 `call_start` 测试。公开工具无法传入号码；服务始终拨打 `VOICE_SIP_CALLEE`。

## 回滚与停机

```bash
systemctl --user disable --now croni-call
```

停机不会删除账号或配置。策略状态位于 `CRONI_POLICY_STATE_FILE`，环境文件和状态文件均应保持 600 权限。
