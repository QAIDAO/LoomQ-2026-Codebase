# Official API source audit

Checked on **2026-08-21 (Asia/Shanghai)**.  Only first-party repositories and
their published source/docs were used to select callable APIs.

## SpinQ

Audited `SpinQTech/spinqit_mcp_tools` at commit
[`3ba2f8c9d16080b738c5eec2d3c93a76334e208e`](https://github.com/SpinQTech/spinqit_mcp_tools/commit/3ba2f8c9d16080b738c5eec2d3c93a76334e208e):

- [README](https://github.com/SpinQTech/spinqit_mcp_tools/blob/3ba2f8c9d16080b738c5eec2d3c93a76334e208e/README.md): Python 3.10 recommendation; `python -m spinqit_mcp_tools.qasm_submitter`; official environment names `PRIVATEKEYPATH`, `SPINQCLOUDUSERNAME`, and `SPINQCLOUDHOST`.
- [setup.py](https://github.com/SpinQTech/spinqit_mcp_tools/blob/3ba2f8c9d16080b738c5eec2d3c93a76334e208e/setup.py): package version `0.0.2`, Python `>=3.10`.
- [qasm_submitter.py](https://github.com/SpinQTech/spinqit_mcp_tools/blob/3ba2f8c9d16080b738c5eec2d3c93a76334e208e/spinqit_mcp_tools/qasm_submitter.py): exact public functions used by the runner; no explicit measure; `Task(..., shots=1000, ...)`; platform fields `pcode`, `simu`, and `countOnlineMachine`; submission/result helpers.

Audited the dependency implementation `SpinQTech/SpinQit` at tree/HEAD commit
[`5f6cd22b6e53ad8c6a9cdc059ed10a6e6919cbf4`](https://github.com/SpinQTech/SpinQit/commit/5f6cd22b6e53ad8c6a9cdc059ed10a6e6919cbf4):

- [spinq_cloud_backend.py](https://github.com/SpinQTech/SpinQit/blob/5f6cd22b6e53ad8c6a9cdc059ed10a6e6919cbf4/spinqit/backend/spinq_cloud_backend.py): live platform parsing, `simu` flag, online-machine guard, accepted task code at `response["task"]["tcode"]`, and result counts at `response["run"]["count"]`.
- [spinq_cloud_client.py](https://github.com/SpinQTech/SpinQit/blob/5f6cd22b6e53ad8c6a9cdc059ed10a6e6919cbf4/spinqit/backend/client/spinq_cloud_client.py): authenticated platform discovery, task creation, status, and result endpoints.

No undocumented SpinQ REST request is constructed by LoomQ; the runner calls the
official submitter surface at runtime.

## OriginQ

Audited `OriginQ/pyqpanda3-skill` at commit
[`130a7237628096526afcc14ddd67c0ded45ee01d`](https://github.com/OriginQ/pyqpanda3-skill/commit/130a7237628096526afcc14ddd67c0ded45ee01d):

- [QCloud service 0.4.0 reference](https://github.com/OriginQ/pyqpanda3-skill/blob/130a7237628096526afcc14ddd67c0ded45ee01d/resources/api/qcloud/service.md): `QCloudService`, `backends()`, `backend()`, `QCloudBackend.run(...)`, and the documented QPU-only restriction on `chip_info()`/`chip_backend()`.
- [QCloud result 0.4.0 reference](https://github.com/OriginQ/pyqpanda3-skill/blob/130a7237628096526afcc14ddd67c0ded45ee01d/resources/api/qcloud/result.md): `get_counts(DataBase.Binary)`, `origin_data()`, `job_id()`, `job_status()`, `error_message()`, and result timing/raw fields.
- [QCloud module index](https://github.com/OriginQ/pyqpanda3-skill/blob/130a7237628096526afcc14ddd67c0ded45ee01d/resources/api/qcloud/index.md): identifies the 0.4.0 workflow changes and public import path.

Audited `OriginQ/QPanda3-doc` at commit
[`40e6397a149671497cdfd2f1206b43dcb1d0eac9`](https://github.com/OriginQ/QPanda3-doc/commit/40e6397a149671497cdfd2f1206b43dcb1d0eac9):

- [OpenQASM converter tutorial](https://github.com/OriginQ/QPanda3-doc/blob/40e6397a149671497cdfd2f1206b43dcb1d0eac9/tutorials/tutorial_04_compilation/tutorial_QASM.markdown): QPanda3 supports OpenQASM 2.0 and exposes `convert_qasm_string_to_qprog(qasm_str) -> QProg`.
- [OriginIR converter tutorial](https://github.com/OriginQ/QPanda3-doc/blob/40e6397a149671497cdfd2f1206b43dcb1d0eac9/tutorials/tutorial_04_compilation/tutorial_OriginIR.markdown): exposes `convert_originir_string_to_qprog(ir_str) -> QProg` and the corresponding file/QProg conversion APIs.  The evidence runner intentionally accepts QASM only, so this verified API is documented but not invoked.
- [hardware-aware transpiler/QCloud tutorial](https://github.com/OriginQ/QPanda3-doc/blob/40e6397a149671497cdfd2f1206b43dcb1d0eac9/tutorials/tutorial_06_quantum_circuit_transpiler/tutorial_root_quantum_circuit_transpiler.markdown): documented `QCloudService`, hardware backend, transpiler/instruction, `run_instruction`, and result path.

The LoomQ OriginQ loader pins `pyqpanda3==0.4.0`; it does not import legacy
`pyqpanda` or an internal `pyqpanda3.qcloud.qcloud` path.
