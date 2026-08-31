# Product facts and implementation decisions

Verified on **2026-08-21**. This file separates facts used by the product UI and
README from marketing inference. Checked-in competition files remain the
authority for scoring; vendor links are supporting context only.

| Claim used in LoomQ Pegasus | Primary source | Decision in this repository |
|---|---|---|
| L1 accepts `spinq`, `originq`, and `braket`, and the formal target dialects are fixed by the starter contract. | [`target_ir_contract.md`](../target_ir_contract.md), [`problem_statement.md`](../../problem_statement.md) | Emit and independently reparse all three dialects; do not infer dialect rules from an SDK. |
| The L2 backend table is the scoring source, including its stable backend IDs. | [`backend_capabilities.json`](../backend_capabilities.json), [`backend_capabilities.md`](../backend_capabilities.md) | Filter the JSON mechanically. Do not hard-code the contradictory 50-qubit prose example. |
| Formal L2 uses an injected OpenAI-compatible endpoint and requires at least one successful model request per case. | [`l2_policy.json`](../l2_policy.json), [`README.md`](../README.md) | Only the injected endpoint is network-enabled; QASM admission and backend selection remain deterministic. |
| SpinQit accepts Python circuits and documents a compile-then-backend execution model; SpinQ also publishes a separate MCP server for SpinQ Cloud QASM submission. | [SpinQTech/SpinQit](https://github.com/SpinQTech/SpinQit), [SpinQTech/spinqit_mcp_tools](https://github.com/SpinQTech/spinqit_mcp_tools) | Keep cloud/QPU tooling optional and credential-gated. The scored offline core does not import either package. |
| The current SpinQ Cloud MCP guide uses `PRIVATEKEYPATH`, `SPINQCLOUDUSERNAME`, and `SPINQCLOUDHOST`, and recommends Python 3.10. | [SpinQ Cloud MCP installation guide](https://github.com/SpinQTech/spinqit_mcp_tools#readme) | Hardware runbooks use those environment names and never persist their values. |
| Current pyqpanda3 QCloud documentation exposes `QCloudService`, QPU backends, `QCloudJob.job_id()`, and result `get_counts()`/`origin_data()` APIs. | [OriginQ QCloud service API](https://github.com/OriginQ/pyqpanda3-skill/blob/main/resources/api/qcloud/service.md), [OriginQ QCloud result API](https://github.com/OriginQ/pyqpanda3-skill/blob/main/resources/api/qcloud/result.md) | The optional OriginQ runner follows that documented surface and is isolated from formal evaluation imports. |
| Amazon Braket accepts OpenQASM 3 on gate devices and provides local simulators. | [AWS OpenQASM guide](https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm.html), [AWS local simulator guide](https://docs.aws.amazon.com/braket/latest/developerguide/braket-send-to-local-simulator.html) | Emit full OpenQASM 3, but use LoomQ's standard-library reference simulator in the Python 3.10 scoring path. |
| The current head of the Amazon Braket Python SDK requires Python 3.11 or newer. | [amazon-braket-sdk-python](https://github.com/amazon-braket/amazon-braket-sdk-python#prerequisites) | Do not add an unverified contemporary Braket SDK pin to the Python 3.10 submission. `braket` results are explicitly identified as LoomQ reference simulation unless a separately validated SDK environment is used. |

## UI wording boundary

The interface may say that a circuit was **translated to a platform dialect**
and **executed by LoomQ's local reference simulator**. It must not say that a
vendor SDK, cloud service, or QPU ran the circuit unless the corresponding raw
response, job ID, backend identity, and timestamp exist in the hardware evidence
bundle. Simulator availability is not evidence of QPU availability.
