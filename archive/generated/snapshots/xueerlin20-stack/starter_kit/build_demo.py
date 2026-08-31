#!/usr/bin/env python3
"""Build a directly-openable demo.html from the real starter_kit/web UI."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DEFAULT_OUTPUT = ROOT.parent / "demo.html"

INDEX_MODULES = (
    "concept-basics.js",
    "onboarding.js",
    "preferences.js",
    "quantum-lab.js",
    "main.js",
)
WORKSPACE_MODULES = (
    "markdown.js",
    "results.js",
    "chat.js",
    "circuit-runner.js",
    "circuit-visualizer.js",
    "conversation-session.js",
    "journey.js",
    "preferences.js",
    "workspace.js",
)

DEMO_API = r"""
const demoConfiguration = {
  ready: true,
  file_error: null,
  fields: [
    {name:'LOOMQ_LLM_BASE_URL',label:'API 根地址',description:'独立 Demo 使用内置模拟响应',default:'demo://local',secret:false,configured:true,value:'demo://local'},
    {name:'LOOMQ_LLM_API_KEY',label:'API Key',description:'独立 Demo 不需要真实凭证',default:'',secret:true,configured:true,value:''},
    {name:'LOOMQ_LLM_MODEL',label:'模型',description:'浏览器内 Demo 模型',default:'loomq-demo',secret:false,configured:true,value:'loomq-demo'},
    {name:'LOOMQ_LLM_TIMEOUT_SECONDS',label:'请求超时',description:'演示值',default:'120',secret:false,configured:true,value:'120'},
  ],
};
const demoState = { conversationId: 'demo_conversation', artifact: null, version: 0 };
function demoCircuit(prompt) {
  const bell = /bell|贝尔/i.test(prompt);
  const requested = prompt.match(/(\d+)\s*(?:比特|qubit)/i);
  const qubits = bell ? 2 : Math.max(2, Math.min(8, requested ? Number(requested[1]) : 3));
  const name = bell ? 'Bell 纠缠电路' : `${qubits} 比特 GHZ 电路`;
  const lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', `qreg q[${qubits}];`, `creg c[${qubits}];`, 'h q[0];'];
  for (let index = 1; index < qubits; index += 1) lines.push(`cx q[${index - 1}],q[${index}];`);
  lines.push('measure q -> c;');
  return {name, qubits, qasm: lines.join('\n')};
}
const api = {
  async getConfiguration() { return structuredClone(demoConfiguration); },
  async saveConfiguration() { return structuredClone(demoConfiguration); },
  async sendChat(payload) {
    await new Promise(resolve => setTimeout(resolve, 360));
    const circuit = demoCircuit(payload.prompt || '');
    demoState.version += 1;
    demoState.artifact = {id:'demo_circuit',version:demoState.version,goal:circuit.name,qubits:circuit.qubits};
    return {
      ok:true, task_type:'generate_qasm', response_language:'zh', qasm:circuit.qasm,
      display_text:`已生成 ${circuit.name}。`, explanation:`已生成 ${circuit.name}。`, validation:{},
      conversation_id:demoState.conversationId, active_artifact:{id:'demo_circuit',version:demoState.version,goal:circuit.name},
      suggestions:['解释每个门的作用','改进当前电路','再运行一次'],
    };
  },
  async runCurrentCircuit(payload) {
    if (!demoState.artifact) throw new Error('请先生成一个电路');
    await new Promise(resolve => setTimeout(resolve, 420));
    const shots = Number(payload.shots || 1024);
    const jitter = Math.round((Math.random() - .5) * Math.sqrt(shots));
    const zero = Math.max(0, Math.min(shots, Math.floor(shots / 2) + jitter));
    const width = demoState.artifact.qubits;
    return {ok:true,backend:'spinq-demo',job_id:'local-demo',shots,counts:{['0'.repeat(width)]:zero,['1'.repeat(width)]:shots-zero}};
  },
  async resetConversation() { demoState.artifact=null; demoState.version=0; return {ok:true,deleted:true}; },
};
"""


def _classic_bundle(module_names: Iterable[str]) -> str:
    pieces = [DEMO_API]
    for name in module_names:
        source = (WEB / "js" / name).read_text(encoding="utf-8")
        source = re.sub(r"^import\s+.+?;\s*$", "", source, flags=re.MULTILINE)
        source = re.sub(r"^export\s+", "", source, flags=re.MULTILINE)
        pieces.append("\n// Source: starter_kit/web/js/%s\n%s" % (name, source))
    return "\n".join(pieces)


def _inline_page(filename: str, module_names: Iterable[str]) -> str:
    html = (WEB / filename).read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="/styles.css">', "<style>\n%s\n</style>" % css)
    bundle = _classic_bundle(module_names)
    if filename == "index.html":
        bundle = bundle.replace(
            "onFinish: () => window.location.assign('/workspace.html'),",
            "onFinish: () => window.parent.postMessage({type:'loomq:navigate',page:'workspace'}, '*'),",
        )
        html = html.replace('href="/workspace.html"', 'href="#workspace" data-demo-workspace')
        bundle += "\ndocument.querySelector('[data-demo-workspace]').addEventListener('click', event => { event.preventDefault(); window.parent.postMessage({type:'loomq:navigate',page:'workspace'}, '*'); });"
    else:
        bundle = bundle.replace("window.location.assign('/?open=config');", "window.parent.postMessage({type:'loomq:navigate',page:'home'}, '*');")
        bundle = bundle.replace("window.location.replace('/?open=config');", "window.parent.postMessage({type:'loomq:navigate',page:'home'}, '*');")
        html = html.replace('href="/?open=config"', 'href="#home" data-demo-home')
        html = html.replace('href="/"', 'href="#home" data-demo-home')
        bundle += "\ndocument.querySelectorAll('[data-demo-home]').forEach(link => link.addEventListener('click', event => { event.preventDefault(); window.parent.postMessage({type:'loomq:navigate',page:'home'}, '*'); }));"
    inline = "<script>\n%s\n</script>" % bundle
    html = re.sub(
        r'<script type="module" src="/js/(?:main|workspace)\.js"></script>',
        lambda _match: inline,
        html,
    )
    return html


def build(output: Path) -> None:
    home = _inline_page("index.html", INDEX_MODULES)
    workspace = _inline_page("workspace.html", WORKSPACE_MODULES)
    fingerprint = hashlib.sha256((home + workspace).encode("utf-8")).hexdigest()[:12]
    home_json = json.dumps(home, ensure_ascii=False).replace("</", "<\\/")
    workspace_json = json.dumps(workspace, ensure_ascii=False).replace("</", "<\\/")
    artifact = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="由 starter_kit/web 生成的 LoomQ 独立 Demo">
  <title>LoomQ Agent · Generated Demo</title>
  <style>html,body,#loomq-demo{width:100%%;height:100%%;margin:0;border:0;background:#0d0e11;overflow:hidden}</style>
</head>
<body>
  <!-- Generated from starter_kit/web; source fingerprint: %s -->
  <iframe id="loomq-demo" title="LoomQ Agent Demo"></iframe>
  <script>
    const pages = {home:%s,workspace:%s};
    const frame = document.querySelector('#loomq-demo');
    function navigate(page) { frame.srcdoc = pages[page] || pages.home; }
    window.addEventListener('message', event => {
      if (event.source === frame.contentWindow && event.data?.type === 'loomq:navigate') navigate(event.data.page);
    });
    navigate('home');
  </script>
</body>
</html>
""" % (fingerprint, home_json, workspace_json)
    output.write_text(artifact, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.output.resolve())
    print("Generated %s from %s" % (args.output.resolve(), WEB))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
