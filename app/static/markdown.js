/* PI-LAB safe Markdown renderer. Model HTML is always plain text. */
(function () {
  "use strict";
  const tokens = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|`([^`\n]+)`|\*\*([^*\n]+)\*\*|__([^_\n]+)__|\*([^*\n]+)\*|_([^_\n]+)_|~~([^~\n]+)~~)/g;
  const make = (tag, text) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    return el;
  };
  function inline(parent, text) {
    let cursor = 0;
    for (const m of text.matchAll(tokens)) {
      const start = m.index;
      if (start > cursor) parent.append(document.createTextNode(text.slice(cursor, start)));
      let node;
      if (m[2] !== undefined) {
        node = make("a", m[2]);
        try {
          const url = new URL(m[3]);
          if (url.protocol === "https:" || url.protocol === "http:") {
            node.href = url.href;
            node.target = "_blank";
            node.rel = "noopener noreferrer";
          } else node = document.createTextNode(m[0]);
        } catch (_) { node = document.createTextNode(m[0]); }
      } else if (m[4] !== undefined) node = make("code", m[4]);
      else if (m[5] !== undefined || m[6] !== undefined) node = make("strong", m[5] ?? m[6]);
      else if (m[7] !== undefined || m[8] !== undefined) node = make("em", m[7] ?? m[8]);
      else node = make("del", m[9]);
      parent.append(node);
      cursor = start + m[0].length;
    }
    if (cursor < text.length) parent.append(document.createTextNode(text.slice(cursor)));
  }
  function paragraph(lines) {
    const el = make("p");
    lines.forEach((line,i) => {
      if (i) el.append(make("br"));
      inline(el,line);
    });
    return el;
  }
  const heading = l => /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(l);
  const item = l => /^(\s*)([-+*]|\d+[.)])\s+(.+)$/.exec(l);
  const quotation = l => /^>\s?(.*)$/.exec(l);
  const fence = l => /^\s{0,3}(`{3,}|~{3,})(.*)$/.exec(l);
  const separator = l => /^\s{0,3}(?:-\s*){3,}$|^\s{0,3}(?:\*\s*){3,}$|^\s{0,3}(?:_\s*){3,}$/.test(l);
  const isBlock = l => heading(l)||item(l)||quotation(l)||fence(l)||separator(l);

  function blocks(root, source) {
    const lines = String(source||"").replace(/\r\n?/g,"\n").split("\n");
    let i=0;
    while (i<lines.length) {
      const line=lines[i];
      if (!line.trim()) {i++;continue;}
      const opening=fence(line);
      if (opening) {
        const marker=opening[1][0], min=opening[1].length;
        const language=opening[2].trim().split(/\s+/)[0].slice(0,36);
        const codeLines=[]; i++;
        const closing=new RegExp("^\\s{0,3}"+marker+"{"+min+",}\\s*$");
        while(i<lines.length&&!closing.test(lines[i])) codeLines.push(lines[i++]);
        if(i<lines.length)i++;
        const wrapper=make("div");wrapper.className="code-block";
        if(language){const label=make("div",language);label.className="code-language";wrapper.append(label);}
        const pre=make("pre");pre.append(make("code",codeLines.join("\n")));
        wrapper.append(pre);root.append(wrapper);continue;
      }
      const h=heading(line);
      if(h){const el=make("h"+h[1].length);inline(el,h[2]);root.append(el);i++;continue;}
      if(separator(line)){root.append(make("hr"));i++;continue;}
      if(quotation(line)){
        const q=[];
        while(i<lines.length&&quotation(lines[i]))q.push(quotation(lines[i++])[1]);
        const b=make("blockquote");b.append(paragraph(q));root.append(b);continue;
      }
      const li=item(line);
      if(li){
        const ordered=/^\d/.test(li[2]), list=make(ordered?"ol":"ul");
        while(i<lines.length){
          const m=item(lines[i]);
          if(!m||/^\d/.test(m[2])!==ordered)break;
          const entry=make("li");inline(entry,m[3]);list.append(entry);i++;
        }
        root.append(list);continue;
      }
      const p=[line];i++;
      while(i<lines.length&&lines[i].trim()&&!isBlock(lines[i]))p.push(lines[i++]);
      root.append(paragraph(p));
    }
  }
  window.PiLabMarkdown={render(target,source){
    const fragment=document.createDocumentFragment();
    blocks(fragment,source);
    target.replaceChildren(fragment);
  }};
})();