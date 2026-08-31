# LoomQ L1 / L2 / L3 submission

This submission implements LoomQ L1, L2, and L3.  The declared contract is
`contract_version: "1.0"`, `starter_kit_version: "1.1.0"`, Python 3.10,
and no L1 network access. L2 uses only the organizer-injected OpenAI-compatible
environment during scoring; L3 is fully local and deterministic.

## Architecture

The L1 path is deliberately small and deterministic:

```text
strict OpenQASM parser -> canonical IR -> exact target emitters
    -> local runners -> canonical normalized counts

L2: OpenAI-compatible model call -> local QASM/backend-id validation -> one repair retry
L3: Hybrid-QASM block parser -> classical AST -> supported RISC-V assembly
```

The targets are `spinq`, `originq`, and `braket`.  Count keys use canonical
classical-bit ordering: the rightmost character is `c[0]`.  For example, a
two-bit key is rendered as `c[1]c[0]`.

SpinQit requires a different `antlr4-python3-runtime` version from the AWS
Braket SDK.  The Docker image intentionally isolates the SpinQ/OriginQ stack
and the Braket stack in separate Python 3.10 runtimes.  Do not install all
four pinned SDK requirements into one shared interpreter.  Docker is the
supported way to install the complete runnable dependency set.

## Working directory and dependency installation

Run the Docker commands below from `starter_kit/`.  The build installs the
pinned runtime dependencies and creates the isolated Braket Python runtime:

```bash
cd starter_kit
docker build -t loomq-l1 .
```

The resulting image is `loomq-l1`.  All Docker test commands run only the
files copied into that image; they do not mount host source code.

## 五分钟新手路线：让谁第一次用上量子计算？

这份项目要让**没有量子 SDK 使用经验、但会运行 Python 或 Docker 命令的
跨学科开发者和学生**第一次把一个量子线路跑通。目标不是让新手猜测术语，
而是先看到“线路 → 重复测量 → 可读结果”的完整链路。

不需要 Key，也不会联网的第一步：

```bash
python -m starter_kit.l2_cli --guide
```

它会用一个 Bell 小实验解释 QASM、后端、模拟器、shots 和真机 QPU，并给出
下一条可执行命令。已有一个 counts JSON 时，可以在本地看简短柱状图和不夸大
结论的说明：

```bash
python -m starter_kit.l2_cli --explain-counts '{"00":4102,"11":4090}'
```

完整的零基础文字路线与术语卡片见
[`newcomer_guide.md`](newcomer_guide.md)。这两个命令不调用 LLM、不需要 API
Key，也不表示已经使用真机。

## Unit tests

From `starter_kit/`, after building the image:

```bash
docker run --rm -w /workspace loomq-l1 python -m unittest discover -s starter_kit/tests -p "test_*.py" -v
```

## Public L1 evaluator

From `starter_kit/`, run every public L1 case against all three local targets:

```bash
docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l1 --target spinq,originq,braket --shots 8192
```

Expected public result: `{"passed": 6, "failed": 0, "total": 6}`.

## L2 assistant

The formal evaluator injects `LOOMQ_LLM_BASE_URL`, `LOOMQ_LLM_API_KEY`, and
`LOOMQ_LLM_MODEL`. Do not put those values in a file or commit them. The agent
makes one model request (and at most one repair request) and accepts only a
parseable OpenQASM 2.0 program or a canonical id from
`starter_kit/backend_capabilities.json`.

Run one interaction after the organizer environment has been configured:

```bash
python -m starter_kit.l2_cli "生成一个 3 比特 GHZ 态并进行全测量"
python -m starter_kit.l2_cli "修复这个 Bell QASM，并返回完整程序：OPENQASM 2.0;"
python -m starter_kit.l2_cli "选择一个免费、本地、至少 20 比特的后端"
```

Without credentials, run the mocked contract and agent tests instead:

```bash
python -m unittest tests.test_l2_contract starter_kit.tests.l2.test_agent starter_kit.tests.l2.test_cli -v
```

### Local provider profiles and model probes

The formal evaluator still reads only `LOOMQ_LLM_BASE_URL`,
`LOOMQ_LLM_API_KEY`, and `LOOMQ_LLM_MODEL`. Local provider profiles are a
CLI-only convenience: they are enabled only by an explicit `--provider` and
temporarily map the provider's own key environment variable to that formal
contract. They never write a key to a file or change the formal evaluation
path.

| `--provider` | Endpoint default | Key read locally from |
|---|---|---|
| `bailian-token-plan` | Token Plan compatible-mode endpoint | `DASHSCOPE_API_KEY` |
| `dashscope` | DashScope compatible-mode endpoint | `DASHSCOPE_API_KEY` |
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `custom` | supplied with `--base-url` | `LOOMQ_LLM_API_KEY` |

For one local Bailian request, with the key already held in your environment:

```bash
python -m starter_kit.l2_cli --provider bailian-token-plan --model qwen3.8-max "生成一个 3 比特 GHZ 态并进行全测量"
```

For a local comparison, provide the candidate IDs yourself. The default is a
dry run: it prints the exact number of calls (three semantic tasks per model)
and makes no network request. Add `--execute` only after confirming the cost.
`--all` means every ID supplied by `--model` or `--models-file`; it never
enumerates a provider's global catalog.

```bash
python -m starter_kit.l2_cli --provider dashscope --probe --all --model qwen-plus --model qwen-max --json
python -m starter_kit.l2_cli --provider dashscope --probe --all --models-file local-models.txt --execute --json
```

The probe checks a three-qubit GHZ distribution, a repaired two-qubit Bell
distribution, and a free, zero-queue canonical backend with at least 15
qubits. It is a local quality signal only; it does not replace the organizer's
private L2 evaluator. Safe errors identify the missing environment variable,
host/timeout, HTTP status/request ID, or QASM/backend validation reason, but
never print an API key, authorization header, or response body.

## L3 Hybrid-QASM

`adapter.compile_hybrid(source)` returns quantum statements in their original
order and RISC-V assembly. The `classical { ... }` subset supports `r1..r9`,
`c[k]`, integers, `+`, `-`, `==`, `!=`, sequential assignments, and nested
`if/else`. Measurement bit `c[k]` maps to `x(10+k)`. Generated assembly uses
only `li`, `add`, `sub`, `addi`, `beq`, `bne`, `j`, and labels.

Run the L3 public check and semantic regression:

```bash
python -m starter_kit.evaluator --level l3
python -m unittest starter_kit.tests.l3 -v
```

For target-specific debugging, run one target at a time from `starter_kit/`:

```bash
docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l1 --target spinq --shots 8192
docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l1 --target originq --shots 8192
docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l1 --target braket --shots 8192
```

## Default Docker verification

From `starter_kit/`, the image default command runs the public L1 evaluator:

```bash
docker build -t loomq-l1 .
docker run --rm loomq-l1
```

It must report the public L1 cases passing.

## Hardware evidence: dry run and import only

There is no live-QPU submission path in this starter kit.  Until an account
API contract, credentials, and provider-issued job ID are available, use only
the local dry-run and evidence-import paths.  They never submit a QPU task.

From `starter_kit/`, a provider dry-run needs no credentials and produces the
exact provider-native program on standard output:

```bash
docker run --rm -w /workspace loomq-l1 python -m starter_kit.hardware.run_qpu --provider spinq --qasm starter_kit/circuits/bell.qasm --shots 8192 --dry-run
docker run --rm -w /workspace loomq-l1 python -m starter_kit.hardware.run_qpu --provider originq --qasm starter_kit/circuits/bell.qasm --shots 8192 --dry-run
docker run --rm -w /workspace loomq-l1 python -m starter_kit.hardware.run_qpu --provider braket --qasm starter_kit/circuits/bell.qasm --shots 8192 --dry-run
```

To import a real provider result after one exists, run the following from the
repository root (the directory containing `starter_kit/`).  The input JSON
must contain the selected provider, a provider-issued non-empty `job_id`, a
UTC timestamp, positive `shots`, and counts summing exactly to `shots`.

```bash
python -m starter_kit.hardware.run_qpu --provider originq --qasm starter_kit/circuits/bell.qasm --shots 8192 --import-result provider-result.json --output-dir starter_kit/evidence/files
```

The importer writes the native program, raw provider result, and normalized
result into `starter_kit/evidence/files/`; it refuses to overwrite existing
artifacts.  Do not put credentials, tokens, cookies, or API keys in source,
evidence, commands, or committed files.
