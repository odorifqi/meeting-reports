/* Diff helpers for the transcript and summary compare views (F17).
   Pure functions, no DOM. Exposed as window.MNDiff (and module.exports for tests). */
(function (root) {
  'use strict';

  // LCS over two arrays with a key function; returns aligned rows [{l, r, li, ri}]
  function align(A, B, key) {
    let pre = 0;
    while (pre < A.length && pre < B.length && key(A[pre]) === key(B[pre])) pre++;
    let suf = 0;
    while (suf < A.length - pre && suf < B.length - pre &&
           key(A[A.length - 1 - suf]) === key(B[B.length - 1 - suf])) suf++;
    const a = A.slice(pre, A.length - suf), b = B.slice(pre, B.length - suf);
    const n = a.length, m = b.length;
    const rows = [];
    for (let i = 0; i < pre; i++) rows.push({ l: A[i], r: B[i], li: i, ri: i });
    if (n && m) {
      const ka = a.map(key), kb = b.map(key);
      const W = m + 1;
      const d = new Uint32Array((n + 1) * W);
      for (let i = n - 1; i >= 0; i--)
        for (let j = m - 1; j >= 0; j--)
          d[i * W + j] = ka[i] === kb[j] ? d[(i + 1) * W + j + 1] + 1
            : Math.max(d[(i + 1) * W + j], d[i * W + j + 1]);
      let i = 0, j = 0;
      while (i < n && j < m) {
        if (ka[i] === kb[j]) { rows.push({ l: a[i], r: b[j], li: pre + i, ri: pre + j }); i++; j++; }
        else if (d[(i + 1) * W + j] >= d[i * W + j + 1]) { rows.push({ l: a[i], r: null, li: pre + i, ri: null }); i++; }
        else { rows.push({ l: null, r: b[j], li: null, ri: pre + j }); j++; }
      }
      while (i < n) { rows.push({ l: a[i], r: null, li: pre + i, ri: null }); i++; }
      while (j < m) { rows.push({ l: null, r: b[j], li: null, ri: pre + j }); j++; }
    } else {
      a.forEach((x, i) => rows.push({ l: x, r: null, li: pre + i, ri: null }));
      b.forEach((x, j) => rows.push({ l: null, r: x, li: null, ri: pre + j }));
    }
    for (let k = 0; k < suf; k++)
      rows.push({ l: A[A.length - suf + k], r: B[B.length - suf + k], li: A.length - suf + k, ri: B.length - suf + k });
    return rows;
  }

  // word diff: returns [[word, changed], ...] for left and right
  function wdiff(a, b) {
    const A = a.split(/\s+/).filter(Boolean), B = b.split(/\s+/).filter(Boolean);
    const n = A.length, m = B.length;
    if (n * m > 250000) return [A.map(w => [w, 1]), B.map(w => [w, 1])];
    const W = m + 1, d = new Uint16Array((n + 1) * W);
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        d[i * W + j] = A[i] === B[j] ? d[(i + 1) * W + j + 1] + 1 : Math.max(d[(i + 1) * W + j], d[i * W + j + 1]);
    let i = 0, j = 0; const L = [], R = [];
    while (i < n && j < m) {
      if (A[i] === B[j]) { L.push([A[i], 0]); R.push([B[j], 0]); i++; j++; }
      else if (d[(i + 1) * W + j] >= d[i * W + j + 1]) L.push([A[i++], 1]);
      else R.push([B[j++], 1]);
    }
    while (i < n) L.push([A[i++], 1]);
    while (j < m) R.push([B[j++], 1]);
    return [L, R];
  }

  /* Transcript rows. Segments keep their id across saves; merge/split change ids.
     txt(seg) decides what counts as "different" (with or without speaker tags). */
  function segBlocks(L, R, txt) {
    const rows = align(L, R, s => s.id);
    // a removed row followed by an added row is shown as one changed line
    const out = [];
    for (let k = 0; k < rows.length; k++) {
      const row = rows[k];
      if (row.l && !row.r && rows[k + 1] && !rows[k + 1].l && rows[k + 1].r) {
        out.push({ l: row.l, r: rows[k + 1].r, li: row.li, ri: rows[k + 1].ri, pair: true });
        k++;
      } else out.push(row);
    }
    const blocks = [];
    let cur = null;
    out.forEach(row => {
      const same = row.l && row.r && txt(row.l) === txt(row.r);
      const kind = same ? 'same' : 'chg';
      if (!cur || cur.kind !== kind) { cur = { kind, rows: [] }; blocks.push(cur); }
      cur.rows.push(row);
    });
    return blocks;
  }

  // Replace the draft segments of one changed block with the left side.
  function revertBlock(draft, block, allBlocks) {
    const ris = block.rows.filter(r => r.ri != null).map(r => r.ri);
    const lefts = block.rows.filter(r => r.l).map(r => JSON.parse(JSON.stringify(r.l)));
    let start, end;
    if (ris.length) { start = Math.min(...ris); end = Math.max(...ris) + 1; }
    else {
      // pure deletion: insert after the last right row before this block
      let pos = 0;
      for (const b of allBlocks) {
        if (b === block) break;
        b.rows.forEach(r => { if (r.ri != null) pos = r.ri + 1; });
      }
      start = end = pos;
    }
    const used = new Set(draft.filter((s, i) => i < start || i >= end).map(s => s.id));
    lefts.forEach(s => { if (used.has(s.id)) s.id = s.id + '-k' + Math.random().toString(36).slice(2, 6); });
    return draft.slice(0, start).concat(lefts, draft.slice(end));
  }

  // Summary markdown -> [{title, lines}] split at "## " headings
  function mdSections(md) {
    const secs = [{ title: 'Judul', lines: [] }];
    (md || '').split('\n').forEach(line => {
      const t = line.trim();
      if (!t) return;
      if (t.startsWith('## ')) secs.push({ title: t.slice(3).trim(), lines: [] });
      else if (/^\|[\s:|-]+\|$/.test(t)) return;          // table separator row
      else secs[secs.length - 1].lines.push(t);
    });
    return secs;
  }

  function sumBlocks(mdA, mdB) {
    const A = mdSections(mdA), B = mdSections(mdB);
    const rows = align(A, B, s => s.title.toLowerCase());
    return rows.map(row => {
      const title = (row.r || row.l).title;
      const la = row.l ? row.l.lines : [], lb = row.r ? row.r.lines : [];
      const lines = align(la, lb, x => x);
      const paired = [];
      for (let k = 0; k < lines.length; k++) {
        const x = lines[k];
        if (x.l != null && x.r == null && lines[k + 1] && lines[k + 1].l == null && lines[k + 1].r != null) {
          paired.push({ l: x.l, r: lines[k + 1].r, li: x.li, ri: lines[k + 1].ri }); k++;
        } else paired.push(x);
      }
      const changed = paired.some(p => p.l !== p.r);
      return { title, rows: paired, changed };
    });
  }

  const api = { align, wdiff, segBlocks, revertBlock, mdSections, sumBlocks };
  root.MNDiff = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
