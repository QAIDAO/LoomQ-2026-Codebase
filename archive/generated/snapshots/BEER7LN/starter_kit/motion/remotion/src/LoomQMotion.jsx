import React from 'react';
import {AbsoluteFill} from 'remotion';

const C = {
  paper: '#F4F0E8', ink: '#172238', purple: '#4B3FA7', coral: '#E5653F',
  teal: '#147D74', muted: '#6A7282', line: '#D6CFC2', white: '#FFFCF6', gold: '#B77A14',
};

export const EXPERIMENTS = {
  'x-flip': {kind: 'paths', title: '普通开关', kicker: 'X：一条确定路线'},
  'hadamard-measure': {kind: 'paths', title: '量子硬币', kicker: 'H：两条测量前路线'},
  'deterministic-baseline': {kind: 'shots', title: '重复按同一个开关', kicker: '每次都得到 1'},
  'randomness-histogram': {kind: 'shots', title: '重复投量子硬币', kicker: '每次只得到一票'},
  'independent-pair': {kind: 'pair', title: '两枚各玩各的', kicker: '独立：四种组合都可能'},
  'bell-state': {kind: 'pair', title: '两枚一起变化', kicker: 'Bell：随机但彼此关联'},
  'phase-zero': {kind: 'phase', title: '箭头同向', kicker: '相位差 0'},
  'phase-half': {kind: 'phase', title: '转四分之一圈', kicker: '相位差 π/2'},
  'phase-flip': {kind: 'phase', title: '转过半圈', kicker: '相位差 π'},
  'bell-2-baseline': {kind: 'chain', title: '先连接两枚', kicker: 'Bell：H → CX'},
  'ghz-3': {kind: 'chain', title: '把第三枚接入', kicker: 'GHZ：H → CX → CX'},
  'ideal-bell-baseline': {kind: 'noise', title: '理想与真实', kicker: '同一 Bell 电路的对照'},
  'ideal-ghz-baseline': {kind: 'noise', title: '电路变长以后', kicker: '理想基线与误差机会'},
};

const clampStep = (value, max = 4) => Math.max(0, Math.min(max, Number(value) || 0));

function Frame({meta, step, children, legend}) {
  return <AbsoluteFill className="lqm-frame" style={{background: C.paper, color: C.ink}}>
    <div className="lqm-grid" />
    <header className="lqm-head">
      <div><span>LOOMQ · 分步图解</span><strong>{meta.title}</strong></div>
      <p>{meta.kicker}</p>
    </header>
    <main className="lqm-stage">{children}</main>
    <footer className="lqm-legend">
      <span><i className="is-now" />本步新增</span>
      <span><i className="is-done" />已经发生</span>
      {legend && <strong>{legend}</strong>}
      <b>步骤 {step + 1}</b>
    </footer>
  </AbsoluteFill>;
}

function Gate({label, current = false, muted = false, color = C.purple}) {
  return <span className={`lqm-gate ${current ? 'is-current' : ''} ${muted ? 'is-muted' : ''}`} style={{'--gate-color': color}}>{label}</span>;
}

function StateNode({value, label, current = false}) {
  return <div className={`lqm-state-node ${current ? 'is-current' : ''}`}><b>{value}</b>{label && <span>{label}</span>}</div>;
}

function Paths({id, meta, step}) {
  const quantum = id === 'hadamard-measure';
  if (step === 4) return <Frame meta={meta} step={step} legend="同样是门，信息路线完全不同">
    <div className="lqm-compare-paths">
      <article><header><Gate label="X" /><b>经典式翻转</b></header><div className="lqm-mini-wire"><span>0</span><i /><Gate label="X" /><i /><span>1</span></div><p>从 0 到 1，始终只有一条确定路线。</p></article>
      <article><header><Gate label="H" /><b>量子式分路</b></header><div className="lqm-mini-branches"><span>0</span><i className="top" /><i className="bottom" /><b>0 路线</b><b>1 路线</b></div><p>测量前由两条带振幅的路线共同决定概率。</p></article>
    </div>
  </Frame>;
  return <Frame meta={meta} step={step} legend={step === 0 ? '门还没有发生' : step < 3 ? '测量尚未发生' : '一次只登记一个结果'}>
    <div className={`lqm-path-diagram ${quantum ? 'is-quantum' : 'is-classical'}`}>
      <div className="lqm-path-axis">
        <StateNode value="0" label="确定起点" current={step === 0} />
        {step >= 1 && <>
          <div className={`lqm-wire-segment before ${step === 1 ? 'is-current' : ''}`} />
          <Gate label={quantum ? 'H' : 'X'} current={step === 1} />
        </>}
        {step >= 1 && !quantum && <>
          <div className={`lqm-wire-segment after ${step === 2 ? 'is-current' : ''}`} />
          <StateNode value="1" label="门后的状态" current={step === 2} />
        </>}
        {step >= 1 && quantum && <div className={`lqm-branch-system ${step === 2 ? 'is-current' : ''}`}>
          <svg viewBox="0 0 560 230" aria-label="H 门后分成两条等大路线">
            <path d="M0 115 C120 115 130 35 280 35 S430 115 560 115" />
            <path d="M0 115 C120 115 130 195 280 195 S430 115 560 115" />
          </svg>
          <span className="route-zero"><b>路线 0</b><small>振幅 1/√2</small></span>
          <span className="route-one"><b>路线 1</b><small>振幅 1/√2</small></span>
        </div>}
        {step >= 3 && <>
          <div className="lqm-measure-link" />
          <div className="lqm-detector is-current"><small>测量一次</small><strong>{quantum ? '0 或 1' : '1'}</strong><span>只记录一个值</span></div>
        </>}
      </div>
      {step === 0 && <div className="lqm-plain-note"><b>现在已知什么？</b><span>qubit 被重新准备为 |0⟩。线路、门和测量都还没有开始。</span></div>}
      {step === 2 && quantum && <div className="lqm-plain-note"><b>不要误读</b><span>两条线代表测量前的两份振幅，不是“一次已经得到 0 和 1”。</span></div>}
    </div>
  </Frame>;
}

const RANDOM_SEQUENCE = ['0','1','1','0','1','0','0','1'];
function VoteBuckets({values, current = false}) {
  return <div className={`lqm-vote-buckets ${current ? 'is-current' : ''}`}>
    {['0','1'].map(label => <section key={label}><header><b>{label}</b><span>{values.filter(v => v === label).length} 票</span></header><div>{values.map((v, i) => v === label && <i key={i}>{v}</i>)}</div></section>)}
  </div>;
}

function Shots({id, meta, step}) {
  const random = id === 'randomness-histogram';
  const sequence = random ? RANDOM_SEQUENCE : RANDOM_SEQUENCE.map(() => '1');
  if (step === 5) return <Frame meta={meta} step={step} legend="shots 增加样本，不改变电路">
    <div className="lqm-shot-compare">
      <article><b>X 电路 · 8 shots</b><VoteBuckets values={RANDOM_SEQUENCE.map(() => '1')} /><p>每次都是 1：确定性结果。</p></article>
      <article><b>H 电路 · 8 shots</b><VoteBuckets values={RANDOM_SEQUENCE} /><p>0 与 1 都出现：单次随机，累计可统计。</p></article>
    </div>
  </Frame>;
  const visibleCount = [0, 0, 1, 2, 8][step];
  const values = sequence.slice(0, visibleCount);
  const flowCount = [1, 2, 3, 3, 3][step];
  return <Frame meta={meta} step={step} legend={step < 2 ? '本轮还没有给 counts 加票' : `${visibleCount} 次独立运行`}>
    <div className="lqm-shots-diagram">
      <div className="lqm-shot-flow">
        {['重新准备 |0⟩','运行电路','测量一次'].map((text, i) => <React.Fragment key={text}>
          {i > 0 && flowCount > i && <i className="lqm-flow-arrow">→</i>}
          {flowCount > i && <div className={`${i === flowCount - 1 && step < 3 ? 'is-current' : 'is-done'}`}><b>0{i + 1}</b><span>{text}</span></div>}
        </React.Fragment>)}
      </div>
      {step >= 2 && <div className="lqm-one-result"><span>这一次</span><b>{sequence[Math.max(0, visibleCount - 1)]}</b><i>只能投进一个桶 ↓</i></div>}
      <VoteBuckets values={values} current={step === 2 || step === 4} />
      {step === 3 && <div className="lqm-loop-note"><b>↺</b><span>丢弃已测量的状态，从新的 |0⟩ 开始下一轮</span></div>}
      {step === 4 && <div className="lqm-counts-equation"><code>counts = {'{'} "0": {values.filter(v => v === '0').length}, "1": {values.filter(v => v === '1').length} {'}'}</code><span>这是 8 张单次选票的累计</span></div>}
    </div>
  </Frame>;
}

function OutcomeGrid({linked, reveal = true, current = false}) {
  return <div className={`lqm-outcome-grid ${current ? 'is-current' : ''}`}>
    {['00','01','10','11'].map(value => {
      const allowed = !linked || value === '00' || value === '11';
      return <div key={value} className={reveal ? (allowed ? 'is-allowed' : 'is-blocked') : ''}><b>{value}</b><span>{!reveal ? '待统计' : allowed ? (linked ? '保留' : '约 25%') : '理想值 0%'}</span></div>;
    })}
  </div>;
}

function Pair({id, meta, step}) {
  const linked = id === 'bell-state';
  return <Frame meta={meta} step={step} legend={step < 3 ? '先看电路关系' : '必须把两枚结果放在一起看'}>
    <div className="lqm-pair-diagram">
      <div className="lqm-pair-circuit">
        {[0,1].map(q => {
          const hasH = q === 0 || !linked;
          return <div className="lqm-qubit-line" key={q}><span>q{q}</span><StateNode value="0" /><i />{step >= 1 && hasH && <Gate label="H" current={step === 1} />}{step >= 1 && <i />}</div>;
        })}
        {step >= 2 && linked && <div className="lqm-cx-node is-current"><b>●</b><i /><strong>⊕</strong><span>CX 建立关联</span></div>}
        {step >= 2 && !linked && <div className="lqm-no-link is-current"><b>不连接</b><span>两条线路各自运行</span></div>}
      </div>
      <div className="lqm-pair-explanation">
        {step === 0 && <div className="lqm-pair-status"><b>00</b><span>两枚都从确定的 0 开始</span></div>}
        {step === 1 && <div className="lqm-marginals"><article><b>q0 单独看</b><span>H 后：0 / 1 各约一半</span></article><article><b>q1 此刻</b><span>{linked ? '仍为 0，等待 CX 传入关联' : 'H 后：0 / 1 各约一半'}</span></article></div>}
        {step >= 2 && <OutcomeGrid linked={linked} reveal={step >= 3} current={step === 3 || step === 4} />}
        {step === 4 && <div className="lqm-pair-rule is-current"><b>{linked ? 'Bell 关联' : '相互独立'}</b><span>{linked ? '单独都随机；合看只保留同面的 00 / 11。' : '知道 q0 的结果，仍不能预测 q1；四种组合都出现。'}</span></div>}
      </div>
    </div>
  </Frame>;
}

function Vector({angle, label, current = false}) {
  return <div className={`lqm-vector-card ${current ? 'is-current' : ''}`}><b>{label}</b><div className="lqm-vector-dial"><i style={{transform: `rotate(${angle}deg)`}}>→</i></div><span>{angle}°</span></div>;
}

function Phase({id, meta, step}) {
  const degrees = id === 'phase-zero' ? 0 : id === 'phase-half' ? 90 : 180;
  const p0 = id === 'phase-zero' ? 100 : id === 'phase-half' ? 50 : 0;
  return <Frame meta={meta} step={step} legend="箭头是振幅模型；测量只能看到概率">
    <div className="lqm-phase-diagram">
      {step === 0 && <div className="lqm-phase-split"><StateNode value="|0⟩" label="输入" /><i /><Gate label="H" current /><div><span>路线 A</span><span>路线 B</span></div></div>}
      {step >= 1 && <div className="lqm-vector-row"><Vector angle={0} label="路线 A" /><b>+</b><Vector angle={step >= 2 ? degrees : 0} label="路线 B" current={step === 2} />{step >= 3 && <><b>=</b><div className="lqm-vector-sum is-current"><i style={{'--sum-angle': `${degrees / 2}deg`, '--sum-scale': degrees === 180 ? 0.08 : degrees === 90 ? 0.7 : 1}}>→</i><span>{degrees === 180 ? '等长反向，彼此抵消' : degrees === 90 ? '只部分同向' : '同向，彼此加强'}</span></div></>}</div>}
      {step === 1 && <div className="lqm-plain-note"><b>箭头读法</b><span>长度 = 振幅大小；方向 = 相位。两支现在一样长、同方向。</span></div>}
      {step === 2 && <div className="lqm-phase-operation"><Gate label="RZ" current /><span>把路线 B 转到 {degrees}°；路线 A 保持 0°</span></div>}
      {step >= 3 && <div className="lqm-recombine"><Gate label="H" current={step === 3} /><span>重新组合路线</span><i>→</i><b>{degrees === 180 ? '0 路线相消' : degrees === 90 ? '0/1 都保留' : '0 路线相长'}</b></div>}
      {step === 4 && <div className="lqm-probability-result is-current"><article><b>P(0)</b><i><span style={{width: `${p0}%`}} /></i><strong>{p0}%</strong></article><article><b>P(1)</b><i><span style={{width: `${100 - p0}%`}} /></i><strong>{100 - p0}%</strong></article></div>}
    </div>
  </Frame>;
}

function CircuitWire({qubits, step, three}) {
  return <div className={`lqm-chain-circuit q-${qubits}`}>
    {Array.from({length: qubits}, (_, q) => <div className="lqm-chain-wire" key={q}><span>q{q}</span><StateNode value="0" /><i /></div>)}
    {step >= 1 && <div className="lqm-chain-h"><Gate label="H" current={step === 1} /><span>q0 分路</span></div>}
    {step >= 2 && <div className={`lqm-chain-cx first ${step === 2 ? 'is-current' : ''}`}><b>●</b><i /><strong>⊕</strong><span>CX 1</span></div>}
    {step >= 3 && three && <div className="lqm-chain-cx second is-current"><b>●</b><i /><strong>⊕</strong><span>CX 2</span></div>}
  </div>;
}

function Chain({id, meta, step}) {
  const three = id === 'ghz-3';
  const qubits = three ? 3 : 2;
  return <Frame meta={meta} step={step} legend="橙色标出本步刚发生的门">
    <div className="lqm-chain-diagram">
      <CircuitWire qubits={qubits} step={step} three={three} />
      <aside>
        {step === 0 && <div className="lqm-chain-state is-current"><b>{'0'.repeat(qubits)}</b><span>唯一的初始状态</span></div>}
        {step === 1 && <div className="lqm-chain-state is-current"><b>0… / 1…</b><span>q0 建立两个候选分支</span></div>}
        {step === 2 && <div className="lqm-support-set is-current"><span>第一次连接后</span><b>00</b><b>11</b></div>}
        {step === 3 && (three ? <div className="lqm-support-set is-current"><span>第二次连接后</span><b>000</b><b>111</b></div> : <div className="lqm-finished-note"><b>Bell-2 已完成</b><span>这个实验没有第三枚 qubit，也不执行第二个 CX。</span></div>)}
        {step === 4 && <div className="lqm-measured-support is-current"><span>重复测量后的主导结果</span><div><b>{'0'.repeat(qubits)}</b><i /><em>约 50%</em></div><div><b>{'1'.repeat(qubits)}</b><i /><em>约 50%</em></div><small>其他组合在理想电路中为 0%</small></div>}
      </aside>
    </div>
  </Frame>;
}

function Bars({counts, label, shots, errorFocus = false}) {
  const labels = ['00','01','10','11'];
  const total = shots || labels.reduce((sum, key) => sum + (Number(counts?.[key]) || 0), 0) || 1;
  return <section className="lqm-data-card"><h3>{label}</h3><div className="lqm-axis-label">占本次 shots 的比例</div><div className="lqm-mini-bars">{labels.map(key => {
    const value = Number(counts?.[key]) || 0;
    const pct = value / total * 100;
    const error = key === '01' || key === '10';
    return <div key={key} className={errorFocus && error ? 'is-current' : ''}><b>{value}</b><i><span style={{height: `${Math.max(value ? 4 : 0, pct)}%`, background: error ? C.coral : C.purple}} /></i><em>{key}</em><small>{pct.toFixed(0)}%</small></div>;
  })}</div></section>;
}

function Noise({id, meta, step, evidence}) {
  const long = id === 'ideal-ghz-baseline';
  const runs = evidence?.runs || [];
  if (long) return <Frame meta={meta} step={step} legend="理想 GHZ-3 · 误差机会分析">
    <div className="lqm-ghz-noise">
      {step === 0 && <div className="lqm-support-set is-current"><span>理想 GHZ-3 支持集</span><b>000</b><b>111</b><small>这是模拟基线，不是真机结果</small></div>}
      {(step === 1 || step === 2) && <div className="lqm-long-circuit">{['H','CX','CX','等待','测量'].map((gate, i) => <React.Fragment key={gate}><Gate label={gate} current={step === 1 && i === 2} color={i > 2 ? C.coral : C.purple}/>{i < 4 && <i />}</React.Fragment>)}</div>}
      {step === 2 && <div className="lqm-error-opportunities">{[['门误差','每次门操作都可能有小偏差'],['退相干','保持越久，量子状态越容易受环境影响'],['读出误差','最终测量也可能把 0/1 读错']].map(([title, copy], i) => <article key={title} className="is-current"><b>0{i + 1}</b><strong>{title}</strong><span>{copy}</span></article>)}</div>}
      {step === 3 && <div className="lqm-interpret-rule is-current"><b>正确结论</b><span>电路更长，只表示误差有更多累积机会；不表示 GHZ 一定失败。</span></div>}
    </div>
  </Frame>;
  const ideal = {'00': 512, '01': 0, '10': 0, '11': 512};
  return <Frame meta={meta} step={step} legend="所有柱图使用 0–100% 的共同纵轴">
    <div className="lqm-noise-diagram">
      {step === 0 && <Bars label="理想模拟 · 1024 shots" counts={ideal} shots={1024} />}
      {step === 1 && <div className="lqm-hardware-route"><div><Gate label="H" /><i /><Gate label="CX" /></div><b>同一份 Bell 电路</b><div className="lqm-hardware-targets"><span>理想模拟器</span><span>本源量子真机</span><span>SpinQ 真机</span></div></div>}
      {step >= 2 && step < 4 && <div className="lqm-noise-bars-grid"><Bars label="理想模拟" counts={ideal} shots={1024} errorFocus={step === 3} />{runs.length ? runs.slice(0, 2).map(run => <Bars key={run.job_id} label={`${run.platform} · 历史真机`} counts={run.counts} shots={run.shots} errorFocus={step === 3} />) : <div className="lqm-evidence-missing"><b>真机证据未载入</b><span>不使用占位 counts。请检查本地 evidence API。</span></div>}</div>}
      {step === 3 && <div className="lqm-noise-meaning is-current"><b>01 / 10 为什么出现？</b><span>门误差 · 退相干 · 读出误差</span><strong>判断重点：00 / 11 是否仍是主峰</strong></div>}
      {step === 4 && <div className="lqm-evidence-step"><div className="lqm-evidence-summary is-current"><b>主峰已核对</b><span>00 / 11 仍占主导；下列字段可回到平台追溯原始任务。</span></div><div className="lqm-job-evidence">{runs.length ? runs.slice(0, 2).map(run => <article key={run.job_id}><b>{run.platform}</b><code>{run.job_id}</code><time>{run.timestamp}</time></article>) : <article><b>证据未载入</b><span>没有 job_id 时不显示伪造内容</span></article>}</div></div>}
    </div>
  </Frame>;
}

export function LoomQMotion({experimentId = 'hadamard-measure', evidence = null, compact = false, stepIndex = 0}) {
  const meta = EXPERIMENTS[experimentId] || EXPERIMENTS['hadamard-measure'];
  const max = meta.kind === 'shots' ? 5 : 4;
  const step = clampStep(stepIndex, max);
  let scene;
  if (meta.kind === 'paths') scene = <Paths id={experimentId} meta={meta} step={step} />;
  else if (meta.kind === 'shots') scene = <Shots id={experimentId} meta={meta} step={step} />;
  else if (meta.kind === 'pair') scene = <Pair id={experimentId} meta={meta} step={step} />;
  else if (meta.kind === 'phase') scene = <Phase id={experimentId} meta={meta} step={step} />;
  else if (meta.kind === 'chain') scene = <Chain id={experimentId} meta={meta} step={step} />;
  else scene = <Noise id={experimentId} meta={meta} step={step} evidence={evidence} />;
  return <AbsoluteFill className={compact ? 'lqm-compact' : ''}>{scene}</AbsoluteFill>;
}
