# Croni Call：初步审计与改造基线

日期：2026-10-28  
工作分支：`croni/remote-mcp`  
上游基线：`yanyan1115/ringringring@311290ddcfb99f46fa8627419e153d616b1defb7`

## 目标

在保留上游 SIP、音频与轮次控制能力的基础上，将本地 STDIO MCP 改造成可由 ChatGPT Chat / Work 使用的受保护远程 MCP。电话服务继续运行在用户控制的 Linux VPS；iPhone 通过 Linphone 接听。

首个可用版本必须做到：

1. 只能呼叫配置中预先登记的 SIP 地址；
2. Chat/Work 可以发起、继续和结束通话；
3. 密钥不进入 Git 仓库、模型上下文或普通日志；
4. 服务重启后自动恢复；
5. 有单线路锁、通话超时、频率限制和静默时段；
6. 所有外部下载均有固定版本和完整性校验；
7. 保留 AGPL-3.0-or-later、Apache-2.0 上游 NOTICE 与 pjproject 许可说明。

## 当前结论

上游实现可作为电话内核继续使用，尤其是：

- pjsua2 / SIP 呼叫流程；
- Linphone + STUN/RTP 连接；
- `call_start`、`converse`、`call_end` 的交互模型；
- 插话检测和轮次控制；
- Groq/OpenAI-compatible STT；
- Edge TTS；
- 单线路文件锁；
- SIP/SDP 日志打码与隐私测试。

上游的 Claude Code 插件外壳和 STDIO 传输不能直接供 ChatGPT 云端使用，需要增加独立远程层。

## 已确认的正向安全措施

- `voice.env` 默认以 0600 权限创建；
- 启动脚本解析配置文件而非 `source` 执行；
- SIP 密码与 STT key 已列入忽略规则；
- 日志默认经过隐私打码；
- 单线路锁可阻止并发重复拨号；
- pjsua2 下载支持 SHA-256 校验；
- 已有 AEC、插话、隐私、STT 与轮次逻辑测试。

## 待整改事项

### P0：远程暴露前必须完成

1. **强制下载校验**  
   当前安装脚本在缺少 `.sha256` 时只给出警告并继续。远程部署版本必须在校验缺失或不匹配时中止。

2. **固定依赖**  
   当前 Python 依赖使用范围约束，首次安装还会升级 pip。部署版本需要锁定直接依赖与关键传递依赖，生成可复现安装清单。

3. **远程身份验证**  
   新增 Streamable HTTP MCP，并使用高强度 Bearer token；后续可升级 OAuth。未经认证的请求不得到达电话内核。

4. **固定被叫白名单**  
   远程工具不得接受任意 SIP 地址。被叫地址只从服务器私密配置读取，工具参数中不暴露 `callee`。

5. **会话所有权与状态隔离**  
   远程请求必须绑定单一已认证用户和单一活动通话；进程重启、客户端断开或超时后自动挂断并释放锁。

6. **频率与时长限制**  
   默认每日呼叫上限、最短重拨间隔、单次最长通话时长、连续失败熔断和静默时段。

7. **秘密与日志边界**  
   SIP 密码、STT key、MCP token 仅存 VPS 私密环境文件；诊断日志默认不记录完整转写文本，原始音频不落盘。

8. **网络边界**  
   MCP 只通过 HTTPS 暴露；电话进程不直接暴露管理端口。防火墙默认拒绝未使用端口。

### P1：首轮可用性

- systemd 服务与自动重启；
- 健康检查端点不返回敏感数据；
- 安装前环境检查；
- 配置验证与可读错误；
- 一键停用远程拨号；
- 失败来电和未接来电的明确状态；
- ChatGPT 插件安装说明；
- VPS 零基础部署文档。

### P2：主动来电

- ChatGPT Scheduled Tasks 接入；
- 静默时段和每日上限；
- 未接后的有限重试；
- 用户可随时暂停；
- 后续接入“满分提醒”打卡状态。

## 拟定架构

```text
ChatGPT Chat / Work / Scheduled Task
                 |
                 | HTTPS + Bearer token
                 v
        Remote MCP gateway
        - authentication
        - allowlist
        - rate limit
        - session ownership
                 |
                 | local-only IPC
                 v
        ringringring phone core
        - pjsua2 / SIP / RTP
        - STT / TTS
                 |
                 v
        sip.linphone.org
                 |
                 v
        Yolie's iPhone / Linphone
```

## 分阶段验收

### 阶段 A：电话内核

- VPS 上以 AI SIP 账号注册；
- iPhone 的接听账号在前台、后台和锁屏时均可响铃；
- 双向音频正常；
- 通话结束后锁释放；
- 服务重启后恢复。

### 阶段 B：远程 MCP

- 未认证请求被拒绝；
- 认证后的 Chat/Work 可调用 `call_start`；
- 任意被叫地址参数被拒绝或根本不存在；
- 三轮语音对话完成；
- 异常断线自动挂断。

### 阶段 C：主动来电

- 定时任务可调用插件；
- 静默时段不拨号；
- 达到每日上限后停止；
- 未接只按既定次数重试；
- 暂停开关立即生效。

## 用户秘密清单

以下值不得提交至仓库，也不得粘贴进聊天：

- 两个 Linphone SIP 密码；
- 邮箱密码与验证码；
- VPS root 密码或 SSH 私钥；
- Groq / STT API key；
- 远程 MCP Bearer token。

仓库只保留变量名、示例值和生成方法。

## 下一步

1. 完成远程层接口设计；
2. 新增安全配置模型与白名单；
3. 强制安装包校验并锁定依赖；
4. 添加远程 MCP 服务骨架；
5. 添加单元测试；
6. 根据实测资源需求选择 VPS。
