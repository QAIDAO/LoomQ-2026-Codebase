// Small, dependency-free Markdown renderer for model-authored chat text.
// It creates DOM nodes and never treats model output as trusted HTML.

export function renderMarkdown(container, source) {
  const lines = String(source || '').replace(/\r\n?/g, '\n').split('\n');
  let paragraph = [];
  let list = null;
  let code = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const node = document.createElement('p');
    appendInline(node, paragraph.join(' '));
    container.append(node);
    paragraph = [];
  };
  const closeList = () => { list = null; };

  lines.forEach((line) => {
    if (code) {
      if (/^\s*```/.test(line)) {
        container.append(code.pre);
        code = null;
      } else {
        code.lines.push(line);
        code.code.textContent = code.lines.join('\n');
      }
      return;
    }

    const fence = line.match(/^\s*```([\w+-]*)\s*$/);
    if (fence) {
      flushParagraph();
      closeList();
      const pre = document.createElement('pre');
      const codeNode = document.createElement('code');
      if (fence[1]) codeNode.dataset.language = fence[1];
      pre.append(codeNode);
      code = { pre, code: codeNode, lines: [] };
      return;
    }
    if (!line.trim()) {
      flushParagraph();
      closeList();
      return;
    }

    const heading = line.match(/^\s*(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      closeList();
      const node = document.createElement(`h${Math.min(heading[1].length + 2, 6)}`);
      appendInline(node, heading[2]);
      container.append(node);
      return;
    }

    const item = line.match(/^\s*([-*+]\s+|\d+[.)]\s+)(.+)$/);
    if (item) {
      flushParagraph();
      const ordered = /^\d/.test(item[1]);
      if (!list || list.tagName !== (ordered ? 'OL' : 'UL')) {
        list = document.createElement(ordered ? 'ol' : 'ul');
        container.append(list);
      }
      const node = document.createElement('li');
      appendInline(node, item[2]);
      list.append(node);
      return;
    }

    const quote = line.match(/^\s*>\s?(.*)$/);
    if (quote) {
      flushParagraph();
      closeList();
      const node = document.createElement('blockquote');
      appendInline(node, quote[1]);
      container.append(node);
      return;
    }

    closeList();
    paragraph.push(line.trim());
  });

  if (code) container.append(code.pre);
  flushParagraph();
  return container;
}

function appendInline(container, text) {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) container.append(document.createTextNode(text.slice(cursor, match.index)));
    const token = match[0];
    let node;
    if (token.startsWith('`')) node = document.createElement('code');
    else if (token.startsWith('**') || token.startsWith('__')) node = document.createElement('strong');
    else node = document.createElement('em');
    const trim = token.startsWith('**') || token.startsWith('__') ? 2 : 1;
    node.textContent = token.slice(trim, -trim);
    container.append(node);
    cursor = match.index + token.length;
  }
  if (cursor < text.length) container.append(document.createTextNode(text.slice(cursor)));
}
