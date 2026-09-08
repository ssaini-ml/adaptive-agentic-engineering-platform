from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["review"])


@router.get("/review/ui", response_class=HTMLResponse, include_in_schema=False)
def review_console() -> HTMLResponse:
    """Small human-facing projection of the append-only review APIs."""
    return HTMLResponse(
        REVIEW_CONSOLE_HTML,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


REVIEW_CONSOLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AAEP evidence review</title>
  <style>
    :root { color-scheme: light; font: 16px/1.5 system-ui, sans-serif; }
    body { margin: 0; color: #17202a; background: #f4f6f7; }
    main { width: min(1100px, calc(100% - 32px)); margin: 32px auto 64px; }
    header, section { background: white; border: 1px solid #dfe6e9; border-radius: 12px;
      box-shadow: 0 2px 10px rgba(23,32,42,.05); }
    header { padding: 24px; border-top: 5px solid #176b5b; }
    section { margin-top: 20px; padding: 20px; }
    h1, h2 { margin-top: 0; }
    h1 { margin-bottom: 4px; font-size: 1.65rem; }
    h2 { font-size: 1.15rem; }
    .meta, .empty { color: #52616b; }
    .count { display: inline-block; min-width: 1.5rem; padding: 1px 7px; margin-left: 4px;
      border-radius: 999px; background: #e7f3f0; color: #0d594c; text-align: center; }
    .item { padding: 16px 0; border-top: 1px solid #edf0f2; }
    .item:first-of-type { border-top: 0; }
    ul { margin-bottom: 0; }
    textarea { display: block; box-sizing: border-box; width: 100%; min-height: 72px;
      margin: 10px 0; padding: 9px; border: 1px solid #aeb7bd; border-radius: 6px; }
    button { padding: 8px 12px; border: 0; border-radius: 6px; color: white;
      background: #176b5b; cursor: pointer; }
    button:disabled { cursor: wait; opacity: .65; }
    a { color: #0b5f90; }
    .notice { padding: 10px 12px; border-radius: 6px; background: #fff8df; }
    .result { margin-left: 8px; color: #176b5b; }
  </style>
</head>
<body>
<main>
  <header>
    <h1>Evidence review</h1>
    <div class="meta">V0.1 abstentions and unresolved references. Feedback is append-only.</div>
  </header>
  <div id="error" class="notice" role="alert" hidden></div>
  <section aria-labelledby="abstentions-heading">
    <h2 id="abstentions-heading">Abstentions <span id="abstention-count" class="count">0</span></h2>
    <div id="abstentions" aria-live="polite"><p class="empty">Loading…</p></div>
  </section>
  <section aria-labelledby="unresolved-heading">
    <h2 id="unresolved-heading">Unresolved references <span id="unresolved-count" class="count">0</span></h2>
    <div id="unresolved" aria-live="polite"><p class="empty">Loading…</p></div>
  </section>
  <section>
    <h2>Candidate rules</h2>
    <p id="candidate-status" class="meta">Loading…</p>
  </section>
</main>
<script>
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
};

function renderEmpty(container, text) {
  container.replaceChildren(node('p', text, 'empty'));
}

function renderAbstentions(items) {
  const container = document.querySelector('#abstentions');
  document.querySelector('#abstention-count').textContent = String(items.length);
  if (!items.length) return renderEmpty(container, 'No abstentions await review.');
  container.replaceChildren();
  for (const item of items) {
    const article = node('article', undefined, 'item');
    article.append(node('strong', item.question));
    const identity = node('div', undefined, 'meta');
    const link = node('a', `Task ${item.task_id}`);
    link.href = `/tasks/${encodeURIComponent(item.task_id)}`;
    identity.append(link, document.createTextNode(` · scan ${item.scan_id}`));
    article.append(identity);
    const list = node('ul');
    for (const gap of item.gaps) list.append(node('li', gap));
    if (item.gaps.length) article.append(list);
    const input = node('textarea');
    input.placeholder = 'Evidence-based reviewer note';
    input.setAttribute('aria-label', `Feedback for ${item.question}`);
    const button = node('button', 'Append feedback');
    const result = node('span', '', 'result');
    button.addEventListener('click', async () => {
      const summary = input.value.trim();
      if (!summary) { result.textContent = 'Enter a reviewer note.'; return; }
      button.disabled = true;
      result.textContent = 'Saving…';
      try {
        const response = await fetch(`/tasks/${encodeURIComponent(item.task_id)}/feedback`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            summary,
            disposition: 'REVIEW_NOTE',
            author_role: 'HUMAN_REVIEWER'
          })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        input.value = '';
        result.textContent = 'Feedback appended.';
      } catch (error) {
        result.textContent = `Could not append feedback: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
    article.append(input, button, result);
    container.append(article);
  }
}

function renderUnresolved(items) {
  const container = document.querySelector('#unresolved');
  document.querySelector('#unresolved-count').textContent = String(items.length);
  if (!items.length) return renderEmpty(container, 'No unresolved references await review.');
  container.replaceChildren();
  for (const item of items) {
    const article = node('article', undefined, 'item');
    article.append(node('strong', item.unresolved_target || '(unnamed target)'));
    article.append(node('div', `Reason: ${item.resolution_reason || 'not recorded'}`));
    article.append(node('div', `Scan ${item.scan_id} · lines ${item.start_line}–${item.end_line}`, 'meta'));
    article.append(node('div', `Relationship ${item.relationship_id}`, 'meta'));
    container.append(article);
  }
}

async function loadReview() {
  try {
    const response = await fetch('/review', {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderAbstentions(data.abstentions);
    renderUnresolved(data.unresolved_references);
    document.querySelector('#candidate-status').textContent = data.candidate_rules_status;
  } catch (error) {
    const alert = document.querySelector('#error');
    alert.textContent = `Review queues could not be loaded: ${error.message}`;
    alert.hidden = false;
    renderEmpty(document.querySelector('#abstentions'), 'Unavailable.');
    renderEmpty(document.querySelector('#unresolved'), 'Unavailable.');
  }
}

loadReview();
</script>
</body>
</html>
"""
