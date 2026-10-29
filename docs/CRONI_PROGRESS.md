# Croni Call：部署进度与实测记录

更新时间：2026-10-29

## 当前里程碑

2026-10-29，Croni Call 在新加坡 Ubuntu 22.04 VPS 上完成首次 ChatGPT Work 端到端双向电话闭环：

1. ChatGPT Work 调用 `call_start`；
2. OpenAI Secure MCP Tunnel 将工具调用转发到 VPS；
3. VPS 通过 Linphone SIP 账号拨打预设的 Yolie 账号；
4. iPhone 接听并正常听到 Edge TTS 中文问候；
5. 用户回答“OK，可以听到”；
6. VPS 上的本地 whisper.cpp 返回转写 `Okay. Okay.`；
7. ChatGPT Work 收到转写，调用 `call_end` 播放结束语并正常挂断。

实测链路如下：

```text
ChatGPT Work
  -> OpenAI Secure MCP Tunnel
  -> VPS stdio MCP
  -> pjsua2 / Linphone SIP
  -> iPhone
  -> VPS 本地 Whisper STT
  -> ChatGPT Work
```

## 当前部署

- VPS：腾讯云轻量应用服务器，新加坡
- 系统：Ubuntu Server 22.04 LTS 64-bit
- 规格：2 vCPU / 2 GB RAM
- 电话：Linphone SIP，固定被叫账号仅保存在 VPS 私密配置
- 远程工具：OpenAI Secure MCP Tunnel，出站 HTTPS，无需开放 MCP 入站端口
- TTS：Edge TTS
- STT：whisper.cpp 1.9.5-dev，`ggml-base.bin` 多语言模型
- 密钥文件：`/etc/croni-call/voice.env` 与 `/etc/croni-call/tunnel.env`，权限 0600
- 服务：`croni-call-tunnel.service`，systemd 自动启动和自动恢复

仓库中的标准本地 STT 安装器为 `deploy/enable-local-whisper.sh`。它使用固定版本、校验模型，并安装更准确的量化 multilingual small 模型；新部署应优先执行该脚本。此次在线迁移为降低手工修复复杂度，先使用 multilingual base 模型完成闭环。

## 本次排障结论

### MCP 启动器未加载 SIP 配置

最初的 `/usr/local/bin/croni-call-mcp` 直接启动 Python，只设置了配置文件路径，未解析其中的 `VOICE_*` 变量。手工测试因此能拨号，而 MCP 工具不能正确初始化电话核心。

修复后改用上游 `plugin-native/bin/run-voice-native.sh`：它以数据方式解析配置文件，再导出环境变量，不会执行配置文件内容。

### 双向通话启用前未安装本地 STT

Stage A 的目标是验证单向拨号与播音，因此不需要 Whisper。进入双向 MCP 测试前还需执行 `deploy/enable-local-whisper.sh`；本次部署流程遗漏了这一过渡步骤，导致接听后进入监听阶段时找不到 `whisper-cli`。

Stage A 安装器现会明确打印本地 STT 安装和诊断命令，避免把“单向测试成功”误认为“双向运行时已经完整”。

## 已知限制

1. **中文识别仍较粗糙。** 首次实测把“OK，可以听到”转写为 `Okay. Okay.`。基础模型已证明链路可用，但会遗漏短中文句。
2. **首次模型加载有延迟。** 服务重启后的第一轮识别需要加载模型，等待时间明显长于后续轮次。
3. **双向对话尚未完成多轮验收。** 当前完成了一轮用户回复及结束语；还需测试连续三轮、插话、静默、用户主动挂断与超时释放。
4. **主动随机来电尚未接入调度。** 目前 ChatGPT Work 可以在对话中直接拨号；定时/随机触发、静默时段和每日上限仍待实现。
5. **回拨尚未实现。** 当前只验证由 Croni Call 主动呼叫用户的方向。

## 下一步顺序

1. 完成三轮中文通话测试并记录延迟、漏词和挂断行为；
2. 比较仓库标准 small 量化模型与当前 base 模型的中文准确率及 2 GB VPS 延迟；
3. 评估“远程 STT 优先、本地 Whisper 兜底”，并保留最小权限密钥；
4. 增加单向通知工具，让任务完成后可以播报一句并立即挂断；
5. 加入静默时段、每日上限、最短重拨间隔和暂停开关；
6. 接入 ChatGPT 自动化，实现受控的不定时主动来电；
7. 调整 TTS 音色，并继续评估实时通话延迟；
8. 新加坡迁移稳定后，撤销香港 VPS 旧密钥、轮换 SIP 密码并安全退役旧实例。
