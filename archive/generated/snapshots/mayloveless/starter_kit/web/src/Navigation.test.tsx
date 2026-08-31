import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AdvancedCapabilityScreen, BackendResults, RepairEvidence, type BackendResponse, type RepairResponse } from './AdvancedCapability'
import { GlobalNavigation } from './Navigation'
import { RecoveryGuidance } from './RecoveryGuidance'

describe('Task 13G-2 global navigation', () => {
  it('gives beginners safe recovery guidance with clear retry and edit actions', () => {
    const markup = renderToStaticMarkup(
      <RecoveryGuidance
        title="这次检查没有完成"
        whatHappened="没有得到可供确认的修复提案。"
        possibleReason="模型服务暂时不可用。"
        nextStep="重试或修改输入。"
        onRetry={() => undefined}
        onModify={() => undefined}
        retryLabel="重试检查"
        modifyLabel="修改目标和程序"
      />,
    )

    expect(markup).toContain('发生了什么')
    expect(markup).toContain('可能原因')
    expect(markup).toContain('下一步操作')
    expect(markup).toContain('重试检查')
    expect(markup).toContain('修改目标和程序')
    expect(markup).toContain('role="alert"')
    expect(markup).not.toMatch(/traceback|API key|\/home\/|LOOMQ_LLM_/i)
  })

  it('always exposes the five-step capability navigation and highlights the current screen', () => {
    const markup = renderToStaticMarkup(<GlobalNavigation current="experiments" onNavigate={() => undefined} />)

    for (const [number, label] of [
      ['01', '认识量子'],
      ['02', '探索实验'],
      ['03', '自由探索'],
      ['04', '程序修复'],
      ['05', '执行平台'],
    ]) {
      expect(markup).toContain(`<span>${number}</span><strong>${label}</strong>`)
    }
    expect(markup).not.toContain('进阶')
    expect(markup).toContain('class="active" aria-current="page"')
    for (const tooltip of [
      '从量子比特和量子门开始，理解量子计算基础概念',
      '通过经典量子实验，观察量子程序如何运行',
      '自由探索量子程序，使用 AI 创建和验证实验',
      '分析并修复已有量子程序的问题',
      '查看量子程序支持的执行平台和运行环境',
    ]) {
      expect(markup).toContain(`title="${tooltip}"`)
    }
  })

  it('renders Repair and Backend as real workspaces without fake execution controls', () => {
    const repair = renderToStaticMarkup(<AdvancedCapabilityScreen kind="repair" onNavigate={() => undefined} />)
    const backend = renderToStaticMarkup(<AdvancedCapabilityScreen kind="backend" onNavigate={() => undefined} />)

    expect(repair).toContain('检查和修复已有量子程序')
    expect(repair).not.toContain('进阶能力 · 即将接入 Web')
    expect(repair).toContain('你希望这段程序做什么？')
    expect(repair).toContain('原始 OpenQASM 2.0')
    expect(repair).toContain('检查并修复')
    expect(backend).toContain('选择合适的运行平台')
    expect(backend).not.toContain('进阶能力 · 即将接入 Web')
    expect(backend).toContain('本地确定性筛选')
    expect(backend).toContain('描述你的运行要求')
    expect(backend).toContain('分析并推荐')
    expect(backend).toContain('这里只做选择，不提交量子任务')
    expect(repair).toContain('<form')
    expect(backend).toContain('<form')
    expect(repair).toContain('<textarea')
    expect(backend).toContain('<textarea')
  })

  it('shows every deterministic backend match without implying a ranking', () => {
    const response: BackendResponse = {
      constraints: { min_qubits: 20, require_qpu: null, require_no_queue: true, cost_policy: 'unspecified', allow_account_required: false },
      matches: [{ id: 'spinq_taurus_simulator', name: 'SpinQ Taurus 本地模拟器', kind: 'simulator', max_qubits: 24, queue: 'none', cost: 'free', requires_account: false, match_reasons: ['24 qubits ≥ 需要的 20', '能力表队列分类为 none'] }],
      excluded: [{ id: 'spinq_cloud_qpu', name: 'SpinQ 云端 QPU', kind: 'qpu', max_qubits: 8, queue: 'minutes_to_hours', cost: 'free_quota', requires_account: true, exclusion_reasons: ['只有 8 qubits，不满足至少 20 qubits'] }],
      no_match: false,
      relaxation_categories: [],
      capability_version: '2026-07',
      events: [],
    }
    const markup = renderToStaticMarkup(<BackendResults response={response} onModify={() => undefined} />)

    expect(markup).toContain('找到 1 个满足全部条件的后端')
    expect(markup).toContain('当前没有排名')
    expect(markup).toContain('SpinQ Taurus 本地模拟器')
    expect(markup).toContain('24 qubits ≥ 需要的 20')
    expect(markup).toContain('只有 8 qubits，不满足至少 20 qubits')
    expect(markup).toContain('version: 2026-07')
    expect(markup).toContain('不代表平台实时状态')
    expect(markup).not.toMatch(/最佳|Top1|最推荐/)
  })

  it('explains no-match honestly and does not invent a candidate', () => {
    const response: BackendResponse = {
      constraints: { min_qubits: 73, require_qpu: true, require_no_queue: true, cost_policy: 'free_only', allow_account_required: false },
      matches: [],
      excluded: [{ id: 'originq_wukong', name: '本源悟空', kind: 'qpu', max_qubits: 72, queue: 'hours', cost: 'free_quota', requires_account: true, exclusion_reasons: ['只有 72 qubits，不满足至少 73 qubits', '能力表队列分类为 hours，不满足零排队'] }],
      no_match: true,
      relaxation_categories: ['比特数', '零排队', '费用', '账号'],
      capability_version: '2026-07',
      events: [],
    }
    const markup = renderToStaticMarkup(<BackendResults response={response} onModify={() => undefined} />)

    expect(markup).toContain('没有同时满足全部条件的后端')
    expect(markup).toContain('可以考虑放宽：比特数、零排队、费用、账号')
    expect(markup).toContain('LoomQ 不会自动修改你的要求')
    expect(markup).not.toContain('满足全部条件</span>')
  })

  it('derives parser and semantic claims only from real trace events', () => {
    const response: RepairResponse = {
      input_validation: { status: 'error', diagnostic: 'ParseError: missing semicolon' },
      reply: 'model explanation',
      repaired_qasm: 'OPENQASM 2.0;\nqreg q[1];',
      events: [
        { seq: 1, layer: 'agent', stage: 'parser_validation', executor: 'local', status: 'ok', summary: 'ok', data: {} },
        { seq: 2, layer: 'agent', stage: 'agent_result', executor: 'local', status: 'ok', summary: 'done', data: { qasm: 'OPENQASM 2.0;\nqreg q[1];', repaired: false } },
      ],
    }
    const markup = renderToStaticMarkup(<RepairEvidence response={response} />)

    expect(markup).toContain('原始程序没有通过本地检查')
    expect(markup).toContain('ParseError: missing semicolon')
    expect(markup).toContain('OpenQASM 语法与结构校验通过')
    expect(markup).toContain('未进行确定性纯态语义验证')
    expect(markup).not.toContain('目标语义验证通过')
    expect(markup).not.toContain('无需修复')
  })

  it('shows real semantic fidelity only for a successful semantic event', () => {
    const response: RepairResponse = {
      input_validation: { status: 'ok', diagnostic: null },
      reply: 'ok',
      repaired_qasm: 'OPENQASM 2.0;\nqreg q[1];',
      events: [
        { seq: 1, layer: 'agent', stage: 'parser_validation', executor: 'local', status: 'ok', summary: 'ok', data: {} },
        { seq: 2, layer: 'agent', stage: 'semantic_verification', executor: 'local', status: 'ok', summary: 'ok', data: { mode: 'statevector', fidelity: 0.998, threshold: 0.97 } },
        { seq: 3, layer: 'agent', stage: 'agent_result', executor: 'local', status: 'ok', summary: 'done', data: { qasm: 'OPENQASM 2.0;\nqreg q[1];' } },
      ],
    }
    const markup = renderToStaticMarkup(<RepairEvidence response={response} />)

    expect(markup).toContain('目标语义验证通过')
    expect(markup).toContain('Fidelity 0.998 · threshold 0.970')
    expect(markup).toContain('原始程序语法可解析')
    expect(markup).not.toContain('程序正确')
  })

  it('does not call an unsupported semantic mode verified', () => {
    const response: RepairResponse = {
      input_validation: { status: 'ok', diagnostic: null },
      reply: 'ok',
      repaired_qasm: 'OPENQASM 2.0;\nqreg q[1];',
      events: [
        { seq: 1, layer: 'agent', stage: 'parser_validation', executor: 'local', status: 'ok', summary: 'ok', data: {} },
        { seq: 2, layer: 'agent', stage: 'semantic_verification', executor: 'local', status: 'ok', summary: 'unsupported', data: { mode: 'unsupported', fidelity: null } },
        { seq: 3, layer: 'agent', stage: 'agent_result', executor: 'local', status: 'ok', summary: 'done', data: { qasm: 'OPENQASM 2.0;\nqreg q[1];' } },
      ],
    }
    const markup = renderToStaticMarkup(<RepairEvidence response={response} />)

    expect(markup).toContain('未进行确定性纯态语义验证')
    expect(markup).not.toContain('目标语义验证通过')
  })
})
