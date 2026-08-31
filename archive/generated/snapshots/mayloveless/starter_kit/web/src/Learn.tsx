import { useEffect, useState, type FocusEvent, type ReactNode } from "react";
import { GlobalNavigation, type AppScreen } from "./Navigation";

type LearnScreenProps = {
  onStart: () => void;
  onNavigate: (screen: AppScreen) => void;
};

type QuantumTermProps = {
  children: ReactNode;
  english: string;
};

// 基础术语只做静态视觉提示，中文始终是主要阅读路径。
function QuantumTerm({ children, english }: QuantumTermProps) {
  return (
    <span className="quantum-term">
      {children}
      {english && <span className="quantum-term-en">（{english}）</span>}
    </span>
  );
}

const RECAP = [
  ["量子比特", "程序正在操作的数据单位"],
  ["量子状态", "程序此刻保留的量子可能性"],
  ["量子门", "改变当前量子状态的操作"],
  ["量子电路", "按顺序组织这些操作的一段程序"],
  ["测量", "把量子状态读取为经典结果"],
];

type LearnStepId = "prepare" | "hadamard" | "measure";

type LearnStep = {
  id: LearnStepId;
  number: string;
  label: string;
  title: string;
  summary: string;
  sourceLine: number;
};

const LEARN_STEPS: LearnStep[] = [
  {
    id: "prepare",
    number: "01",
    label: "Prepare",
    title: "准备 |0⟩",
    summary: "程序先准备一个确定的量子状态。",
    sourceLine: 3,
  },
  {
    id: "hadamard",
    number: "02",
    label: "H",
    title: "产生叠加",
    summary: "H 把原本确定的 |0⟩ 变成同时保留两种可能性的状态。",
    sourceLine: 5,
  },
  {
    id: "measure",
    number: "03",
    label: "Measure",
    title: "读取结果",
    summary: "测量把量子状态读取成经典的 0 或 1。",
    sourceLine: 6,
  },
];

const QASM_LINES = [
  "OPENQASM 2.0;",
  'include "qelib1.inc";',
  "qreg q[1];",
  "creg c[1];",
  "h q[0];",
  "measure q[0] -> c[0];",
];

type LearnProbabilityRowProps = {
  basis: string;
  probability: number;
  subdued?: boolean;
  animate?: boolean;
};

// 概率条只表达教学中的状态分布，不模拟真实的物理运动。
function LearnProbabilityRow({
  basis,
  probability,
  subdued = false,
  animate = false,
}: LearnProbabilityRowProps) {
  return (
    <div
      className={`learn-compact-probability${subdued ? " is-subdued" : ""}${animate ? " is-animated" : ""}`}
    >
      <code>{basis}</code>
      <i>
        <b style={{ width: `${probability}%` }} />
      </i>
      <strong>{probability}%</strong>
    </div>
  );
}

function LearnStateVisual({ step }: { step: LearnStepId }) {
  if (step === "hadamard") {
    return (
      <div
        className="learn-compact-state-change"
        aria-label="H 执行前后从百分之百的零态变为零态和一态各百分之五十"
      >
        <div className="learn-compact-snapshot">
          <span>执行前</span>
          <LearnProbabilityRow basis="|0⟩" probability={100} />
          <LearnProbabilityRow basis="|1⟩" probability={0} subdued />
        </div>
        <div className="learn-compact-gate">
          <strong>H</strong>
          <i>→</i>
        </div>
        <div className="learn-compact-snapshot is-after">
          <span>执行后 · 叠加</span>
          <LearnProbabilityRow basis="|0⟩" probability={50} animate />
          <LearnProbabilityRow basis="|1⟩" probability={50} animate />
        </div>
      </div>
    );
  }

  if (step === "measure") {
    return (
      <div
        className="learn-compact-measurement"
        aria-label="一次测量与重复运行的区别"
      >
        <div>
          <span>一次运行</span>
          <strong>
            0 <i>或</i> 1
          </strong>
          <p>普通程序只收到一个确定的 bit。</p>
        </div>
        <i className="learn-compact-divider" />
        <div>
          <span>重复 1,000 次 · shots</span>
          <LearnProbabilityRow basis="0" probability={50} />
          <LearnProbabilityRow basis="1" probability={50} />
          <p>多次结果汇总后，才形成统计分布。</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="learn-compact-prepare"
      aria-label="初始量子状态为零态百分之百"
    >
      <span>当前量子状态 · 确定</span>
      <LearnProbabilityRow basis="|0⟩" probability={100} />
      <LearnProbabilityRow basis="|1⟩" probability={0} subdued />
      <p>
        此时测量只会得到 <code>0</code>。
      </p>
    </div>
  );
}

type RealHardwareCapability = {
  spinq: {
    available: boolean;
    reason: string;
  };
};

type RealHardwareJob = {
  job_id: string;
  status: "submitted" | "running" | "completed" | "failed";
  platform: "spinq";
  result: Record<string, unknown>;
};

const REAL_HARDWARE_POLL_MS = 5000;

function realResultEntries(result: Record<string, unknown>) {
  const probabilities = result.probabilities;
  if (!probabilities || typeof probabilities !== "object" || Array.isArray(probabilities)) {
    return [];
  }
  return Object.entries(probabilities)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number")
    .sort(([left], [right]) => left.localeCompare(right));
}

type RealHardwareModalProps = {
  open: boolean;
  onClose: () => void;
};

// 真机体验仅使用既有 API；它不参与 Explorer 的模拟实验状态。
function RealHardwareModal({ open, onClose }: RealHardwareModalProps) {
  const [capability, setCapability] = useState<RealHardwareCapability | null>(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(false);
  const [job, setJob] = useState<RealHardwareJob | null>(null);
  const [pollError, setPollError] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);

  const loadCapability = async () => {
    setCapabilityError(false);
    setCapability(null);
    try {
      const response = await fetch("/api/real-hardware/status");
      if (!response.ok) throw new Error("status unavailable");
      const payload = (await response.json()) as RealHardwareCapability;
      if (!payload.spinq || typeof payload.spinq.available !== "boolean") {
        throw new Error("invalid status payload");
      }
      setCapability(payload);
    } catch {
      setCapabilityError(true);
    }
  };

  useEffect(() => {
    if (open) void loadCapability();
  }, [open]);

  useEffect(() => {
    if (!open || !job || (job.status !== "submitted" && job.status !== "running")) {
      return undefined;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      setPollError(false);
      try {
        const response = await fetch(`/api/real-hardware/status/${encodeURIComponent(job.job_id)}`);
        if (!response.ok) throw new Error("job status unavailable");
        const payload = (await response.json()) as Omit<RealHardwareJob, "platform">;
        if (!payload.job_id || !["running", "completed", "failed"].includes(payload.status)) {
          throw new Error("invalid job payload");
        }
        if (!cancelled) {
          setJob({ ...payload, platform: "spinq" });
          if (payload.status === "running") timer = setTimeout(() => void poll(), REAL_HARDWARE_POLL_MS);
        }
      } catch {
        if (!cancelled) setPollError(true);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [job?.job_id, job?.status, open, pollAttempt]);

  const startExperiment = async () => {
    setSubmitting(true);
    setSubmitError(false);
    try {
      const response = await fetch("/api/real-hardware/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ circuit: "bell", platform: "spinq" }),
      });
      if (!response.ok) throw new Error("submission failed");
      const payload = (await response.json()) as Omit<RealHardwareJob, "result">;
      if (!payload.job_id || payload.status !== "submitted" || payload.platform !== "spinq") {
        throw new Error("invalid submission payload");
      }
      setJob({ ...payload, result: {} });
    } catch {
      setSubmitError(true);
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;
  const entries = job ? realResultEntries(job.result) : [];

  return (
    <div className="real-hardware-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="real-hardware-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="real-hardware-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button className="real-hardware-close" type="button" onClick={onClose} aria-label="关闭真实量子计算体验">×</button>
        <span>REAL HARDWARE · OPTIONAL EXPERIENCE</span>
        <h2 id="real-hardware-title">让你的第一个量子程序运行在真实量子芯片上</h2>

        {capabilityError && (
          <div className="real-hardware-message is-error" role="alert">
            <strong>暂时无法连接真实量子设备。</strong>
            <p>请检查网络后重试；你仍可以继续使用模拟实验。</p>
            <button type="button" onClick={() => void loadCapability()}>重新检查</button>
          </div>
        )}

        {!capability && !capabilityError && <p className="real-hardware-loading">正在检查真实量子设备连接…</p>}

        {capability && !capability.spinq.available && (
          <div className="real-hardware-message">
            <strong>真实量子实验需要连接 SpinQ Cloud。</strong>
            <p>当前运行环境未配置真实量子设备。你仍可以继续使用模拟实验。</p>
          </div>
        )}

        {capability?.spinq.available && !job && (
          <div className="real-hardware-ready">
            <dl>
              <div><dt>实验</dt><dd>Bell State</dd></div>
              <div><dt>设备</dt><dd>SpinQ Cloud</dd></div>
            </dl>
            <p>该实验将在真实量子芯片执行，完成时间取决于设备队列。</p>
            {submitError && <p className="real-hardware-inline-error" role="alert">提交没有完成。请检查网络后重试。</p>}
            <button className="learn-primary" type="button" onClick={() => void startExperiment()} disabled={submitting}>
              {submitting ? "正在提交…" : "开始运行"}
            </button>
          </div>
        )}

        {job && (job.status === "submitted" || job.status === "running") && (
          <div className="real-hardware-waiting" aria-live="polite">
            <strong>任务已提交</strong>
            <p>Job ID: <code>{job.job_id}</code></p>
            <p>正在等待真实量子设备执行…</p>
            {pollError && <button type="button" onClick={() => setPollAttempt((value) => value + 1)}>重新查询</button>}
          </div>
        )}

        {job?.status === "completed" && (
          <div className="real-hardware-result" aria-live="polite">
            <strong>这是来自真实量子设备的运行结果</strong>
            <small className="real-hardware-note">有限次测量与真机噪声会带来波动，不一定恰为 50%。</small>
            <p>Job ID: <code>{job.job_id}</code> · 平台 SpinQ · 执行完成</p>
            {entries.length ? (
              <div className="real-hardware-probabilities" aria-label="真实设备测量结果">
                {entries.map(([basis, probability]) => (
                  <div key={basis}>
                    <code>{basis}</code><i><b style={{ width: `${Math.max(0, Math.min(100, probability * 100))}%` }} /></i><strong>{(probability * 100).toFixed(1)}%</strong>
                  </div>
                ))}
              </div>
            ) : <p>任务已完成，平台返回的原始结果已保存。</p>}
          </div>
        )}

        {job?.status === "failed" && (
          <div className="real-hardware-message is-error" role="alert">
            <strong>真实量子设备未能完成该任务。</strong>
            <p>你可以稍后重试；这不会影响模拟实验。</p>
            <button type="button" onClick={() => setJob(null)}>重新开始</button>
          </div>
        )}
      </section>
    </div>
  );
}

export function LearnScreen({ onStart, onNavigate }: LearnScreenProps) {
  const [activeStepId, setActiveStepId] = useState<LearnStepId>("prepare");
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourcePinned, setSourcePinned] = useState(false);
  const [realHardwareOpen, setRealHardwareOpen] = useState(false);
  const activeStep =
    LEARN_STEPS.find((step) => step.id === activeStepId) ?? LEARN_STEPS[0];

  const selectStep = (stepId: LearnStepId) => {
    setActiveStepId(stepId);
    setSourceOpen(false);
    setSourcePinned(false);
  };

  const toggleSource = () => {
    const nextPinned = !sourcePinned;
    setSourcePinned(nextPinned);
    setSourceOpen(nextPinned);
  };

  const handleSourceBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget) && !sourcePinned) {
      setSourceOpen(false);
    }
  };

  return (
    <main className="learn-shell">
      <GlobalNavigation current="learn" onNavigate={onNavigate} />

      <section className="learn-landing">
        <div className="learn-landing-copy">
          <span className="learn-eyebrow">
            QUANTUM COMPUTING ·{" "}
            <QuantumTerm english="">FOR DEVELOPERS</QuantumTerm>
          </span>
          <h1>
            从熟悉的编程方式开始
            <br />
            理解量子计算
          </h1>
          <p>量子计算不是更快的普通电脑，而是一种面向特定问题的新计算方式。</p>
          <p>
            LoomQ 帮助<QuantumTerm english="">开发者</QuantumTerm>
            从熟悉的编程方式出发，探索、生成并验证量子程序。
          </p>
          <div className="learn-landing-actions">
            <a
              className="learn-primary learn-guide-link"
              href="#learn-quickstart"
            >
              30 秒看懂一个量子程序 <span>↓</span>
            </a>
            <button className="learn-landing-secondary" onClick={onStart}>
              直接选择实验 <span>→</span>
            </button>
          </div>
        </div>
        <div
          className="learn-product-flow"
          aria-label="LoomQ 从用户意图到理解测量结果的探索流程"
        >
          <span>YOUR INTENT</span>
          <div>
            <strong>用户描述目标</strong>
            <code>目标 · 问题</code>
          </div>
          <i>
            ↓ <em>EXPLORE</em>
          </i>
          <span>QUANTUM PROGRAM</span>
          <div>
            <strong>生成并验证量子程序</strong>
            <code>结构 · 语义</code>
          </div>
          <i>
            ↓ <em>TRACE</em>
          </i>
          <span>EXECUTION TRACE</span>
          <div>
            <strong>探索程序如何执行</strong>
            <code>状态 · 步骤</code>
          </div>
          <i>
            ↓ <em>READ</em>
          </i>
          <span>RESULT</span>
          <div>
            <strong>理解测量结果</strong>
            <code>读出 · 分布</code>
          </div>
        </div>
      </section>

      {/* 三步教学只保留一套交互骨架，状态变化优先于源码。 */}
      <section
        className="learn-quickstart"
        id="learn-quickstart"
        aria-labelledby="learn-quickstart-heading"
      >
        <header className="learn-quickstart-heading">
          <div>
            <span>ONE QUBIT · THREE STEPS</span>
            <h2 id="learn-quickstart-heading">
              跟着一个<QuantumTerm english="">量子比特</QuantumTerm>
              ，看懂量子程序怎么运行
            </h2>
            <p>
              不需要量子物理背景。先观察每一步的状态变化，需要时再查看它对应的真实源码。
            </p>
          </div>
          <aside>
            <strong>
              什么是
              <QuantumTerm english="Quantum Circuit">量子电路</QuantumTerm>？
            </strong>
            <p>可以先理解成：按顺序执行的一组量子操作。</p>
          </aside>
        </header>

        <div
          className="learn-compact-steps"
          role="tablist"
          aria-label="单量子比特程序的三个步骤"
        >
          {LEARN_STEPS.map((step, index) => (
            <div className="learn-compact-step-slot" key={step.id}>
              <button
                type="button"
                role="tab"
                aria-selected={activeStepId === step.id}
                className={activeStepId === step.id ? "is-active" : ""}
                onClick={() => selectStep(step.id)}
              >
                <span>{step.number}</span>
                <strong>{step.label}</strong>
                <small>{step.title}</small>
              </button>
              {index < LEARN_STEPS.length - 1 && <i aria-hidden="true">→</i>}
            </div>
          ))}
        </div>

        <div className="learn-compact-workspace">
          <article className="learn-compact-copy" aria-live="polite">
            <span>
              STEP {activeStep.number} · {activeStep.label.toUpperCase()}
            </span>
            <h3>{activeStep.title}</h3>
            <p>{activeStep.summary}</p>
            {activeStepId === "prepare" && (
              <small>
                这个<QuantumTerm english="Qubit">量子比特</QuantumTerm>从确定的{" "}
                <code>|0⟩</code> 开始。
              </small>
            )}
            {activeStepId === "hadamard" && (
              <small>
                同时保留两种可能性，就叫
                <QuantumTerm english="Superposition">叠加</QuantumTerm>。
              </small>
            )}
            {activeStepId === "measure" && (
              <small>
                一次测量只得到一个结果；统计分布来自重复运行的{" "}
                <QuantumTerm english="Shots">采样次数</QuantumTerm>。
              </small>
            )}

            <div
              className={`learn-source-wrap${sourcePinned ? " is-pinned" : ""}`}
              onMouseEnter={() => setSourceOpen(true)}
              onMouseLeave={() => !sourcePinned && setSourceOpen(false)}
              onFocusCapture={() => setSourceOpen(true)}
              onBlurCapture={handleSourceBlur}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setSourceOpen(false);
                  setSourcePinned(false);
                }
              }}
            >
              <button
                type="button"
                className="learn-source-trigger"
                aria-expanded={sourceOpen}
                aria-controls="learn-qasm-source"
                onClick={toggleSource}
              >
                查看源码 <span>{sourceOpen ? "−" : "+"}</span>
              </button>
              <div
                className="learn-source-popover"
                id="learn-qasm-source"
                role="region"
                aria-label="完整 OpenQASM 源码"
                hidden={!sourceOpen}
              >
                <header>
                  <strong>one-qubit.qasm</strong>
                  <small>当前步骤对应第 {activeStep.sourceLine} 行</small>
                </header>
                <div>
                  {QASM_LINES.map((line, index) => (
                    <p
                      className={
                        index + 1 === activeStep.sourceLine
                          ? "is-highlighted"
                          : ""
                      }
                      key={line}
                    >
                      <em>{String(index + 1).padStart(2, "0")}</em>
                      <code>{line}</code>
                    </p>
                  ))}
                </div>
              </div>
            </div>
          </article>

          <div className="learn-compact-visual" key={activeStepId}>
            <header>
              <span>量子状态变化</span>
              <small>{activeStep.number} / 03</small>
            </header>
            <LearnStateVisual step={activeStepId} />
          </div>
        </div>
      </section>

      <section className="learn-recap" aria-labelledby="recap-heading">
        <div className="learn-recap-intro">
          <span>NOW NAME THE PARTS</span>
          <h2 id="recap-heading">你刚刚已经读完了第一个量子电路</h2>
          <p>
            现在只是给刚才已经看懂的内容补上名字。每个术语，都能在这段程序的执行过程中找到位置。
          </p>
        </div>
        <dl className="learn-recap-list">
          {RECAP.map(([name, copy]) => (
            <div key={name}>
              <dt>
                <strong>{name}</strong>
              </dt>
              <dd>{copy}</dd>
            </div>
          ))}
        </dl>
      </section>

      <details className="learn-technical">
        <summary>
          <span>
            <i>+</i>
            <strong>想看更技术一点？</strong>
          </span>
          <small>默认收起 · 只讲运行模型</small>
        </summary>
        <div className="learn-technical-grid">
          <p>
            <code>2^n</code>
            <span>n 个 qubit 的纯态，可以用长度 2ⁿ 的复振幅状态向量表示。</span>
          </p>
          <p>
            <code>Gate</code>
            <span>量子门对状态向量做确定性的变换。</span>
          </p>
          <p>
            <code>|a|²</code>
            <span>测量按振幅模平方对应的概率进行采样。</span>
          </p>
          <p>
            <code>shots</code>
            <span>重复运行和测量，会得到 counts 与概率直方图。</span>
          </p>
        </div>
      </details>

      <section className="learn-bottom-cta">
        <span>READY TO EXPLORE</span>
        <h2>
          你已经能读懂量子程序
          <br />
          最基本的执行过程。
        </h2>
        <p>
          进入 Explorer
          后，可以逐步运行更完整的电路，同时观察每条指令和量子状态变化。
        </p>
        <button className="learn-primary" onClick={onStart}>
          选择一个量子实验 <span>→</span>
        </button>
        <button className="learn-real-hardware-entry" type="button" onClick={() => setRealHardwareOpen(true)}>
          🚀 体验真实量子计算
        </button>
      </section>
      <RealHardwareModal open={realHardwareOpen} onClose={() => setRealHardwareOpen(false)} />
    </main>
  );
}
