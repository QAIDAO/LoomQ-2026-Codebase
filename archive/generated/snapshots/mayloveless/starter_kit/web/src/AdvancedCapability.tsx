import { useRef, useState, type FormEvent } from 'react'
import { GlobalNavigation, type AppScreen } from './Navigation'
import { RecoveryGuidance } from './RecoveryGuidance'
import type { TraceEvent } from './types'

type AdvancedCapabilityProps = {
  kind: 'repair' | 'backend'
  onNavigate: (screen: AppScreen) => void
}

export type RepairResponse = {
  input_validation: { status: 'ok' | 'error'; diagnostic: string | null }
  reply: string
  repaired_qasm: string | null
  events: TraceEvent[]
}

type BackendConstraints = {
  min_qubits: number | null
  require_qpu: boolean | null
  require_no_queue: boolean
  cost_policy: 'free_only' | 'free_or_quota' | 'paid_allowed' | 'unspecified'
  allow_account_required: boolean | null
}

type BackendFact = {
  id: string
  name: string
  kind: string
  max_qubits: number
  queue: string
  cost: string
  requires_account: boolean
}

type MatchedBackend = BackendFact & { match_reasons: string[] }
type ExcludedBackend = BackendFact & { exclusion_reasons: string[] }

export type BackendResponse = {
  constraints: BackendConstraints
  matches: MatchedBackend[]
  excluded: ExcludedBackend[]
  no_match: boolean
  relaxation_categories: string[]
  capability_version: string
  events: TraceEvent[]
}

const BROKEN_BELL_QASM = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];`

const BACKEND_EXAMPLES = [
  '至少 20 个 qubit，不想排队，也不想注册账号。',
  '我想用真实量子硬件，8 个 qubit 就够，可以排队，也可以使用免费额度并注册账号。',
  '只想本地免费运行，不需要真实量子硬件。',
]

function latestEvent(events: TraceEvent[], stage: string): TraceEvent | undefined {
  return [...events].reverse().find((event) => event.layer === 'agent' && event.stage === stage)
}

export function RepairEvidence({ response }: { response: RepairResponse }) {
  const parser = latestEvent(response.events, 'parser_validation')
  const semantic = latestEvent(response.events, 'semantic_verification')
  const agentResult = latestEvent(response.events, 'agent_result')
  const semanticSupported = semantic?.data.mode === 'statevector'
  const semanticPassed = semantic?.status === 'ok' && semanticSupported
  const semanticFailed = semantic?.status === 'error'
  const reliableAgentResult = agentResult?.status === 'ok' && Boolean(response.repaired_qasm)
  const fidelity = typeof semantic?.data.fidelity === 'number' ? semantic.data.fidelity : null
  const threshold = typeof semantic?.data.threshold === 'number' ? semantic.data.threshold : null

  return (
    <div className="repair-evidence">
      <section className={`repair-check ${response.input_validation.status}`}>
        <span>原始程序检查</span>
        {response.input_validation.status === 'ok' ? (
          <><strong>原始程序语法可解析</strong><p>LoomQ 会继续根据你描述的目标检查并生成修复提案。</p></>
        ) : (
          <><strong>原始程序没有通过本地检查</strong><code>{response.input_validation.diagnostic}</code></>
        )}
      </section>

      <section className="repair-verification">
        <span>验证结果</span>
        <div className={parser?.status === 'ok' ? 'ok' : parser?.status === 'error' ? 'error' : 'neutral'}>
          <b>{parser?.status === 'ok' ? '✓' : parser?.status === 'error' ? '×' : '—'}</b>
          <div>
            <strong>{parser?.status === 'ok'
              ? 'OpenQASM 语法与结构校验通过'
              : parser?.status === 'error'
                ? 'OpenQASM 语法与结构校验失败'
                : '未记录 OpenQASM 语法与结构校验'}</strong>
            {parser?.status === 'error' && parser.data.diagnostic != null && <code>{String(parser.data.diagnostic)}</code>}
          </div>
        </div>
        <div className={semanticPassed ? 'ok' : semanticFailed ? 'error' : 'neutral'}>
          <b>{semanticPassed ? '✓' : semanticFailed ? '×' : '—'}</b>
          <div>
            <strong>{semanticPassed
              ? '目标语义验证通过'
              : semanticFailed
                ? '目标语义验证失败'
                : '未进行确定性纯态语义验证'}</strong>
            {semanticPassed && fidelity != null && (
              <small>Fidelity {fidelity.toFixed(3)}{threshold != null ? ` · threshold ${threshold.toFixed(3)}` : ''}</small>
            )}
            {semanticFailed && semantic.data.diagnostic != null && <code>{String(semantic.data.diagnostic)}</code>}
          </div>
        </div>
        <div className={reliableAgentResult ? 'ok' : 'neutral'}>
          <b>{reliableAgentResult ? '✓' : '—'}</b>
          <div><strong>{reliableAgentResult ? '最终候选已通过 production pipeline' : '未取得可靠的最终候选'}</strong></div>
        </div>
      </section>
    </div>
  )
}

export function RepairWorkspace({ onNavigate }: { onNavigate: (screen: AppScreen) => void }) {
  const [goal, setGoal] = useState('')
  const [qasm, setQasm] = useState('')
  const [response, setResponse] = useState<RepairResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [applied, setApplied] = useState(false)
  const goalInputRef = useRef<HTMLTextAreaElement>(null)

  function loadExample() {
    setGoal('生成 Bell 态并测量两个量子比特')
    setQasm(BROKEN_BELL_QASM)
    setResponse(null)
    setError('')
    setApplied(false)
  }

  async function submitRepair(event?: FormEvent) {
    event?.preventDefault()
    const requestGoal = goal.trim()
    const requestQasm = qasm.trim()
    if (!requestGoal || !requestQasm || loading) return
    setLoading(true)
    setError('')
    setResponse(null)
    setApplied(false)
    try {
      const result = await fetch('/api/repair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: requestGoal, qasm: requestQasm }),
      })
      const payload = await result.json() as RepairResponse & { error?: string }
      if (!result.ok) throw new Error(payload.error)
      setResponse(payload)
    } catch {
      setError('这次检查没有完成，请检查模型配置后重试。')
    } finally {
      setLoading(false)
    }
  }

  function applyRepair() {
    if (!response?.repaired_qasm) return
    // 修复提案只有在用户明确确认后才写回编辑区，不自动发起第二次请求。
    setQasm(response.repaired_qasm)
    setApplied(true)
  }

  function modifyRepairInput() {
    setError('')
    goalInputRef.current?.focus()
  }

  return (
    <main className="repair-shell">
      <GlobalNavigation current="repair" onNavigate={onNavigate} />
      <header className="repair-heading">
        <div><span>04 · CHECK & REPAIR</span><h1>检查和修复已有量子程序</h1></div>
        <p>粘贴 OpenQASM 并说明原本目标。LoomQ 会给出经过真实 parser 与语义验证路径检查的修复提案，是否应用由你决定。</p>
      </header>

      <form className="repair-workspace" onSubmit={submitRepair}>
        <section className="repair-input-panel">
          <header><span>ORIGINAL</span><button type="button" onClick={loadExample} disabled={loading}>加载示例</button></header>
          <label htmlFor="repair-goal">你希望这段程序做什么？</label>
          <textarea id="repair-goal" ref={goalInputRef} className="repair-goal-input" placeholder="例如：生成 Bell 态并测量两个量子比特" value={goal} onChange={(event) => { setGoal(event.target.value); setApplied(false) }} disabled={loading} />
          <label htmlFor="repair-qasm">原始 OpenQASM 2.0</label>
          <textarea id="repair-qasm" className="repair-qasm-input" spellCheck={false} placeholder={'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];'} value={qasm} onChange={(event) => { setQasm(event.target.value); setApplied(false) }} disabled={loading} />
          <button className="repair-submit" type="submit" disabled={loading || !goal.trim() || !qasm.trim()}>{loading ? '正在检查…' : '检查并修复'}</button>
        </section>

        <section className="repair-result-panel" aria-live="polite">
          <header><span>REPAIR RESULT</span><strong>{loading ? '正在准备修复提案' : response ? '检查完成' : '等待输入'}</strong></header>
          {loading && <div className="repair-loading"><i aria-hidden="true" /><h2>正在检查并准备修复提案</h2><p>LoomQ 会先理解目标，再让修复后的程序经过本地验证。</p></div>}
          {!loading && error && (
            <RecoveryGuidance
              title="这次检查没有完成"
              whatHappened="LoomQ 没有得到可供你确认的修复提案。"
              possibleReason="模型服务暂时不可用、网络连接中断，或本地验证环境尚未准备好。"
              nextStep="可以直接重试；若问题仍然存在，请检查目标说明和 OpenQASM 后再提交。"
              onRetry={() => void submitRepair()}
              onModify={modifyRepairInput}
              retryLabel="重试检查"
              modifyLabel="修改目标和程序"
            />
          )}
          {!loading && !error && !response && <div className="repair-empty"><span>粘贴已有程序</span><i>→</i><span>查看修复提案</span><i>→</i><span>确认后应用</span></div>}
          {!loading && response && (
            <div className="repair-result-content">
              <RepairEvidence response={response} />
              <section className="repair-proposal">
                <div><span>LoomQ 的修复提案</span>{response.repaired_qasm && <small>来自真实 agent_result</small>}</div>
                {response.repaired_qasm ? <pre><code>{response.repaired_qasm}</code></pre> : <p>本次没有取得可靠的最终 OpenQASM，因此不提供可应用的修复提案。</p>}
                {response.repaired_qasm && <div className="repair-apply-row"><button type="button" onClick={applyRepair}>应用修复到编辑区</button>{applied && <span>✓ 已应用到编辑区</span>}</div>}
              </section>
            </div>
          )}
        </section>
      </form>
    </main>
  )
}

function kindLabel(kind: string): string {
  return kind === 'qpu' ? '真机 QPU' : kind === 'simulator' ? '模拟器' : kind === 'cloud' ? '云端' : kind
}

function queueLabel(queue: string): string {
  return queue === 'none' ? 'none · 无排队' : queue === 'hours' ? 'hours · 小时级' : queue === 'minutes_to_hours' ? 'minutes_to_hours · 分钟至小时' : queue
}

function costLabel(cost: string): string {
  return cost === 'free' ? 'free · 免费' : cost === 'free_quota' ? 'free_quota · 免费额度' : cost === 'paid' ? 'paid · 付费' : cost
}

function constraintRows(constraints: BackendConstraints): Array<[string, string]> {
  const costLabels: Record<BackendConstraints['cost_policy'], string> = {
    free_only: '仅完全免费',
    free_or_quota: '免费或免费额度',
    paid_allowed: '允许付费',
    unspecified: '未限制成本策略',
  }
  return [
    ['最少 qubits', constraints.min_qubits == null ? '未指定' : `至少 ${constraints.min_qubits}`],
    ['设备类型', constraints.require_qpu == null ? '未限制设备类型' : constraints.require_qpu ? '必须使用真机 QPU' : '不要求必须为真机'],
    ['队列要求', constraints.require_no_queue ? '要求零排队' : '未要求零排队'],
    ['成本策略', costLabels[constraints.cost_policy]],
    ['账号要求', constraints.allow_account_required == null ? '未限制账号要求' : constraints.allow_account_required ? '允许需要账号的后端' : '不允许需要账号'],
  ]
}

function BackendFacts({ backend }: { backend: BackendFact }) {
  return (
    <dl className="backend-facts">
      <div><dt>类型</dt><dd>{kindLabel(backend.kind)}</dd></div>
      <div><dt>最大 qubits</dt><dd>{backend.max_qubits}</dd></div>
      <div><dt>队列分类</dt><dd>{queueLabel(backend.queue)}</dd></div>
      <div><dt>成本分类</dt><dd>{costLabel(backend.cost)}</dd></div>
      <div><dt>账号</dt><dd>{backend.requires_account ? '需要账号' : '无需账号'}</dd></div>
    </dl>
  )
}

export function BackendResults({ response, onModify }: { response: BackendResponse; onModify: () => void }) {
  return (
    <div className="backend-result-content">
      <section className="backend-constraints">
        <header><span>LoomQ 理解到的约束</span><small>来自 backend_constraints Trace</small></header>
        <div>{constraintRows(response.constraints).map(([label, value]) => <p key={label}><span>{label}</span><strong>{value}</strong></p>)}</div>
        <footer>AI 只负责理解你的要求；具体后端由本地能力表确定。</footer>
      </section>

      <section className={`backend-matches${response.no_match ? ' no-match' : ''}`}>
        <header>
          <div>
            <span>满足条件的后端</span>
            <h2>{response.no_match ? '当前能力表中没有同时满足全部条件的后端。' : `找到 ${response.matches.length} 个满足全部条件的后端`}</h2>
          </div>
          {response.no_match && <button type="button" onClick={onModify}>修改要求后重新分析</button>}
        </header>
        {!response.no_match && <p className="backend-order-note">以下为全部匹配项，按官方能力表顺序展示；当前没有排名。</p>}
        {response.no_match && <p className="backend-relaxation">可以考虑放宽：{response.relaxation_categories.join('、')}。LoomQ 不会自动修改你的要求。</p>}
        <div className="backend-match-list">
          {response.matches.map((backend) => (
            <article className="backend-match-card" key={backend.id}>
              <header><div><h3>{backend.name}</h3><code>{backend.id}</code></div><span>满足全部条件</span></header>
              <BackendFacts backend={backend} />
              {backend.match_reasons.length > 0 && <ul>{backend.match_reasons.map((reason) => <li key={reason}>✓ {reason}</li>)}</ul>}
            </article>
          ))}
        </div>
      </section>

      <section className="backend-excluded">
        <header><span>其他后端为什么没有入选</span><small>{response.excluded.length} 个</small></header>
        <div>
          {response.excluded.map((backend) => (
            <article key={backend.id}>
              <div><h3>{backend.name}</h3><code>{backend.id}</code></div>
              <BackendFacts backend={backend} />
              <ul>{backend.exclusion_reasons.map((reason) => <li key={reason}>× {reason}</li>)}</ul>
            </article>
          ))}
        </div>
      </section>

      <p className="backend-snapshot-note">能力数据来自 LoomQ 官方后端能力表快照（version: {response.capability_version}）。队列、成本等为评测基准分类，不代表平台实时状态。</p>
    </div>
  )
}

export function BackendWorkspace({ onNavigate }: { onNavigate: (screen: AppScreen) => void }) {
  const [prompt, setPrompt] = useState('')
  const [response, setResponse] = useState<BackendResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const promptInputRef = useRef<HTMLTextAreaElement>(null)

  async function submitBackend(event?: FormEvent) {
    event?.preventDefault()
    const requestPrompt = prompt.trim()
    if (!requestPrompt || loading) return
    setLoading(true)
    setError('')
    setResponse(null)
    try {
      const result = await fetch('/api/backend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: requestPrompt }),
      })
      const payload = await result.json() as BackendResponse & { error?: string }
      if (!result.ok) throw new Error(payload.error)
      setResponse(payload)
    } catch {
      setError('这次推荐没有完成，请检查模型配置后重试。')
    } finally {
      setLoading(false)
    }
  }

  function modifyBackendInput() {
    setError('')
    promptInputRef.current?.focus()
  }

  return (
    <main className="backend-shell">
      <GlobalNavigation current="backend" onNavigate={onNavigate} />
      <header className="backend-heading">
        <div><span>05 · SELECT BACKEND</span><h1>选择合适的运行平台</h1></div>
        <p>告诉 LoomQ 你的 qubit、真机、排队、成本和账号限制。AI 只提取标准约束，候选与排除原因由本地能力表确定。</p>
      </header>
      <form className="backend-workspace" onSubmit={submitBackend}>
        <section className="backend-input-panel">
          <header><span>REQUIREMENTS</span><strong>自然语言 → 标准约束</strong></header>
          <label htmlFor="backend-prompt">描述你的运行要求</label>
          <textarea id="backend-prompt" ref={promptInputRef} placeholder="例如：至少 20 个 qubit，不想排队，也不想注册账号。" value={prompt} onChange={(event) => setPrompt(event.target.value)} disabled={loading} />
          <button className="backend-submit" type="submit" disabled={loading || !prompt.trim()}>{loading ? '正在分析…' : '分析并推荐'}</button>
          <div className="backend-examples">
            <span>示例要求</span>
            {BACKEND_EXAMPLES.map((example, index) => <button type="button" key={example} onClick={() => { setPrompt(example); setError('') }} disabled={loading}><b>{index + 1}</b>{example}</button>)}
          </div>
          <aside><strong>这里只做选择，不提交量子任务</strong><p>不会查询实时队列、实时价格或平台可用性。</p></aside>
        </section>
        <section className="backend-result-panel" aria-live="polite">
          <header><span>RECOMMENDATION</span><strong>{loading ? '正在分析要求' : response ? '本地筛选完成' : '等待输入'}</strong></header>
          {loading && <div className="backend-loading"><i aria-hidden="true" /><h2>正在理解要求并筛选能力表</h2><p>请求完成后会一次性展示真实约束和本地筛选结果。</p></div>}
          {!loading && error && (
            <RecoveryGuidance
              title="这次推荐没有完成"
              whatHappened="LoomQ 没有得到可解释的后端筛选结果。"
              possibleReason="模型服务暂时不可用、网络连接中断，或本地能力表校验未完成。"
              nextStep="可以直接重试；若仍未完成，请修改运行要求后再分析。"
              onRetry={() => void submitBackend()}
              onModify={modifyBackendInput}
              retryLabel="重试分析"
              modifyLabel="修改运行要求"
            />
          )}
          {!loading && !error && !response && <div className="backend-empty"><span>描述运行要求</span><i>→</i><span>AI 提取约束</span><i>→</i><span>本地确定性筛选</span></div>}
          {!loading && response && <BackendResults response={response} onModify={() => setResponse(null)} />}
        </section>
      </form>
    </main>
  )
}

export function AdvancedCapabilityScreen({ kind, onNavigate }: AdvancedCapabilityProps) {
  if (kind === 'repair') return <RepairWorkspace onNavigate={onNavigate} />
  return <BackendWorkspace onNavigate={onNavigate} />
}
