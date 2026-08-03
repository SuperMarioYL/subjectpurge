<div align="right"><sub><b>简体中文</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.en.md">English</a></sub></div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="清痕 SubjectPurge — per-subject 删除溯源与等保审计">
</picture>

<p align="center"><sub>为信创 / 政企团队跨 agent 记忆库定位并清除个人 PII 的删除溯源器，全程数据不出境。</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="license"></a>
  <img src="https://img.shields.io/github/v/release/SuperMarioYL/subjectpurge?label=release" alt="release">
  <img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/subjectpurge/ci.yml?branch=main&label=ci" alt="ci">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="python">
  <img src="https://img.shields.io/badge/on--prem-no--cloud-red" alt="on-prem">
  <img src="https://img.shields.io/badge/PIPL--47-audit%20ready-ff9f0a" alt="PIPL-47">
</p>

> **删除请求来了，agent 记忆里某人的 PII 散落在 7 个地方——清痕 30 秒定位、可追溯删除并签发等保审计证明，全程不出境。**

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="架构：CLI → 扫描器·适配器 → Audit 签名">
</picture>

一个进程。适配器是进程内插件，实现 `locate(subject) -> [ResidueHit]`（及 m2 的 `purge(hit)`）。
扫描器扇出到每个注册存储，合并结果写入 `residue_map.json`；purger 逐命中删除并写链式 `lineage.jsonl`；
audit 用 ed25519 签发等保2.0 证明。可选的 LLM（Qwen2.5-7B-Instruct，OpenAI 兼容端点，**默认关闭**）
只在 `trace_ref` 残留需要模糊匹配时调用——等保证明不能建立在模型之上。

agent 记忆不再是单一关系表，而是 SQLite + 向量索引 + 压缩轨迹的异构存储。
MemPalace / claude-mem 主导的是 ingest → recall 方向，没人拥有 recall → delete 的反向索引——
清痕补上这一段：给定一个主体标识（手机号 / 身份证号 / 邮箱），跨异构存储定位其全部 PII 残留、
可追溯删除并签发审计证明，且**全部在数据不出境边界内**完成。

| 能力 | [MemPalace](https://github.com/MemPalace/mempalace) / [claude-mem](https://github.com/thedotmack/claude-mem) | 手动 SQL 脚本 | 清痕 |
|---|---|---|---|
| ingest → recall 质量 | ✓（更强，二者以此见长） | partial | — |
| per-subject 反向定位 | — | partial（仅单表） | ✓ |
| 跨异构存储（图/向量/轨迹） | partial（仅自有存储） | — | ✓ |
| 链式哈希 + ed25519 审计证明 | — | — | ✓（m3） |
| 数据不出境 / 离线 | partial | ✓ | ✓ |

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 安装</h2>

```bash
git clone https://github.com/SuperMarioYL/subjectpurge && cd subjectpurge
pip install -e ".[chroma]"        # 核心 + Chroma 适配器；纯核心用 pip install -e .
```

> 信创环境若访问 GitHub 受限，用 Gitee 镜像：`git clone https://gitee.com/SuperMarioYL/subjectpurge`。
> Chroma 文档以显式 dummy embedding 写入，定位方向**不下载任何 embedding 模型**，完全离线。

<h2>快速开始</h2>

```bash
python examples/seed_demo.py /tmp/sp-demo                 # 造一个 3-store fixture（7 处残留）
subjectpurge scan --subject 13800138000 --config /tmp/sp-demo/stores.yaml
```

<details><summary>样例输出</summary>

```
scanned subject=13800138000 across 3 store(s), operator=sre-alice
scan complete: subject=13800138000
  total residue hits: 7
  claude_mem: 3 hit(s)
  trace_logs: 2 hit(s)
  vec_index: 2 hit(s)
  residue_kind=direct_pii: 1
  residue_kind=embedded: 3
  residue_kind=summarized: 1
  residue_kind=trace_ref: 2
  residue map -> /tmp/sp-demo/residue_map.json
```
</details>

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

四个子命令对应删除请求的完整生命周期。**m1 已交付 `scan`**；`purge` / `audit` / `verify` 为脚手架（m2 / m3）：

```bash
# m1 —— 定位：给定主体，跨注册存储输出 residue_map.json
subjectpurge scan   --subject 13800138000 --config stores.yaml --out residue_map.json

# m2 —— 删除：逐命中删除 + 链式哈希 lineage.jsonl（before/after 计数；幂等）
subjectpurge purge  --subject 13800138000 --config stores.yaml --confirm --out lineage.jsonl

# m3 —— 审计：ed25519 签名 + 等保2.0 报告；verify 离线往返
subjectpurge audit  --subject 13800138000 --residue residue_map.json --lineage lineage.jsonl
subjectpurge verify audit_proof.json   # exit 0 = 验证通过
```

配置 `stores.yaml` 指向本机 agent 记忆运行时（claude-mem SQLite 路径、Chroma 持久目录、轨迹文本 glob）：

```yaml
operator: sre-alice
law_ref: PIPL-47
stores:
  - id: claude_mem
    kind: sqlite
    path: /var/agent/claude-mem.db
    table: memories
    text_columns: [session, phone, content, summary]
  - id: vec_index
    kind: chroma
    path: /var/agent/chroma
    collection: sessions
  - id: trace_logs
    kind: trace_text
    glob: "/var/agent/trace/**/*.log"
```

<h2><img src="https://api.iconify.design/tabler:adjustments.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 配置</h2>

`stores.yaml` 顶层键：

| key | type | default | 含义 |
|---|---|---|---|
| `operator` | str | `operator` | 合规 / SRE 账号，写入审计记录 |
| `law_ref` | str | `PIPL-47` | 审计证明引用的法规（`PIPL-47` / `CCPA-1798.105` / `GDPR-17`） |
| `stores` | list | `[]` | 注册的 agent-memory 存储 |

每个 `stores[]` 条目：

| key | type | default | 含义 |
|---|---|---|---|
| `id` | str | — | 存储 id，出现在 `residue_map.json` 与 `lineage.jsonl` |
| `kind` | `sqlite` \| `chroma` \| `trace_text` \| `graph` | — | 适配器类型（`graph` 为企业扩展，v0.1 不内置） |
| `path` | str | — | 文件 / 目录路径（sqlite、chroma） |
| `collection` | str | `sessions` | chroma collection 名 |
| `glob` | str | — | trace-text glob（支持 `**` 递归） |
| `table` | str | `memories` | sqlite 表名 |
| `text_columns` | list | `[content, summary, text]` | sqlite 扫描的文本列 |

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Demo</h2>

反向删除的 10 分钟 happy path：seeded 3-store fixture（SQLite×3 + Chroma×2 + Trace×2 = 7 处残留）
→ `scan` 输出 residue_map → `purge` / `audit` / `verify`（m2 / m3 脚手架）。

![清痕 reverse-delete demo](assets/demo.gif)

原始终端录制：[assets/demo.cast](./assets/demo.cast)（asciinema v2，可用 `asciinema play assets/demo.cast` 播放，或在线 [asciinema.org](https://asciinema.org) 查看）。
GIF 由 [`docs/demo.tape`](./docs/demo.tape)（vhs 脚本）经 `.github/workflows/demo.yml` 渲染，手动重跑刷新。

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **m1 定位主体**：scanner + 3 适配器（SQLite / Chroma / Trace）→ `residue_map.json`，fixture 7 处跨 3 库
- [ ] **m2 删除溯源**：purger 逐命中删除 + append-only 链式哈希 `lineage.jsonl`（`prior_hash` / `self_hash` + before/after 计数），重扫显示 0 残留
- [ ] **m3 审计证明**：ed25519 detached 签名 + 等保2.0 jinja2 报告（CN-primary）+ `verify` 离线往返
- [ ] **企业扩展**：图存储适配器（Neo4j / JanusGraph）+ 等保厂商控制台集成（绿盟 / 启明星辰）+ 多运行时联邦 + 驻场部署

## 付费

OSS 核心（3 适配器 + CLI + residue_map + ed25519 验证）永久免费。**清痕本身从不被云托管**——
`数据不出境` 从架构上禁止了云托管 SaaS。付费的是按组织（per-org，非 per-seat）的**企业扩展许可证**：

- **图存储适配器**：Neo4j / JanusGraph 接入（v0.1 仅 SQLite + 向量 + 轨迹）
- **等保厂商控制台集成**：绿盟 / 启明星辰 / 天融信 控制台
- **多运行时联邦**：跨 >1 个 agent 运行时的删除溯源
- **驻场部署支持**：信创 on-prem 环境的部署、调优、SLA

信创企业按组织买全站许可，不走 Stripe——合同 / 对公转账。最小成单路径：一个省级政务云 / 国资行信创团队
用 OSS 核心跑通一次真实个保法删除请求后，签一份 ¥3 万试点部署合同，扩展至 ¥8–15 万 / 组织 / 年。
有意试点请在 [Issues](https://github.com/SuperMarioYL/subjectpurge/issues) 留言或在企业微信 / 对公渠道联系。

> **诚实的杀手假设**：若网信办 / 个保法指引认定"编码后的 embedding / summary = 已匿名"，
> 删除义务对大部分异构残留将失效。我们在 LOC > 2k 前过 lawyer gate，并为"原始文本 / 轨迹残留无论如何在范围内"
> 的更窄立场而构建。

<h2><img src="https://api.iconify.design/tabler:license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> License</h2>

MIT，见 [LICENSE](./LICENSE)。欢迎在 [Issues](https://github.com/SuperMarioYL/subjectpurge/issues)
反馈 bug、提议适配器或上报 fixture。企业扩展 / 驻场部署请见上方「付费」节。

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
