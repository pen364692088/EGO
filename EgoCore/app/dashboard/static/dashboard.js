const view = document.body.dataset.view;
const sampleId = document.body.dataset.sampleId;
const metaBar = document.getElementById("meta-bar");
const app = document.getElementById("app");
const POLL_MS = 8000;

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderMeta(buildMeta, gapSummary) {
  const items = [
    ["Total Runs", buildMeta.total_runs],
    ["Complete E4 Bundles", buildMeta.complete_runs],
    ["OE Available", buildMeta.oe_available_runs],
    ["Host-only", buildMeta.host_only_runs],
    ["Failure Cases", buildMeta.failure_cases],
  ];
  metaBar.innerHTML = items
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <strong>${escapeHtml(value ?? 0)}</strong>
          <span>${escapeHtml(label)}</span>
        </article>
      `,
    )
    .join("");
  if (gapSummary?.continuity_status) {
    metaBar.innerHTML += Object.entries(gapSummary.continuity_status)
      .map(
        ([label, value]) => `
          <article class="stat-card">
            <strong>${escapeHtml(value)}</strong>
            <span>continuity:${escapeHtml(label)}</span>
          </article>
        `,
      )
      .join("");
  }
}

function gapTag(type) {
  if (type.includes("missing") || type.includes("gap")) return "warning";
  if (type.includes("mismatch")) return "danger";
  return "ok";
}

function renderRuns(records, continuity) {
  if (!records.length) {
    app.innerHTML = `<section class="panel"><div class="empty">当前没有 runs 索引。</div></section>`;
    return;
  }
  const continuityMap = new Map(continuity.map((item) => [item.scenario, item.status]));
  app.innerHTML = `
    <section class="panel">
      <h2>Live Runs</h2>
      <p>实时样本流，按只读派生索引展示 bundle 完整度、continuity 命中和关键 gap。</p>
      <div class="pill-row">
        ${[...continuityMap.entries()]
          .map(([scenario, status]) => `<span class="pill ${status === "missing" ? "warning" : "ok"}">${escapeHtml(`continuity:${scenario}=${status}`)}</span>`)
          .join("")}
      </div>
    </section>
    <section class="row-list">
      ${records
        .map(
          (record) => `
            <a class="row-link" href="/samples/${encodeURIComponent(record.sample_id)}">
              <strong>${escapeHtml(record.sample_id)}</strong>
              <span class="muted">${escapeHtml(record.timestamp)}</span>
              <div class="tag-list">
                <span class="tag ${record.bundle_complete ? "ok" : "warning"}">${record.bundle_complete ? "complete_bundle" : "partial_bundle"}</span>
                <span class="tag ${record.oe_available ? "ok" : "warning"}">${record.oe_available ? "oe_available" : "oe_unavailable"}</span>
                ${record.host_only ? `<span class="tag warning">host_only</span>` : ""}
                ${record.repair_closure ? `<span class="tag ok">repair_closure</span>` : ""}
                ${(record.continuity_tags || []).map((tag) => `<span class="tag ok">${escapeHtml(tag)}</span>`).join("")}
                ${(record.gap_types || []).map((tag) => `<span class="tag ${gapTag(tag)}">${escapeHtml(tag)}</span>`).join("")}
              </div>
            </a>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderGrowth(records, summary) {
  if (!records.length) {
    app.innerHTML = `<section class="panel"><div class="empty">当前没有可用的 OE growth records。</div></section>`;
    return;
  }
  app.innerHTML = `
    <section class="panel">
      <h2>Growth Signals</h2>
      <p>只展示可审计的 OpenEmotion 结构化信号，不做“意识程度”解释。</p>
      <div class="pill-row">
        <span class="pill ok">records=${escapeHtml(summary.total_records)}</span>
        <span class="pill ${summary.reflection_trigger_count ? "ok" : "warning"}">reflection_triggers=${escapeHtml(summary.reflection_trigger_count)}</span>
        <span class="pill ${summary.repair_closure_count ? "ok" : "warning"}">repair_closure=${escapeHtml(summary.repair_closure_count)}</span>
      </div>
    </section>
    <section class="detail-grid">
      ${records
        .map(
          (record) => `
            <article>
              <h3>${escapeHtml(record.sample_id)}</h3>
              <p class="muted">${escapeHtml(record.timestamp)}</p>
              <pre>${escapeHtml(JSON.stringify({
                memory_update: record.memory_update_summary,
                appraisal_state_delta: record.appraisal_delta_summary,
                reflection: record.reflection_summary,
                response_tendency: record.response_tendency_summary,
                cycle: record.cycle_summary,
              }, null, 2))}</pre>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderFailures(records, gapSummary) {
  app.innerHTML = `
    <section class="panel">
      <h2>Failures & Replay</h2>
      <p>真实 failure cases 与 bundle gap 分开显示，避免把缺项误记成失败。</p>
      <pre>${escapeHtml(JSON.stringify(gapSummary, null, 2))}</pre>
    </section>
    <section class="row-list">
      ${records.length
        ? records
            .map(
              (record) => `
                <article class="row-link">
                  <strong>${escapeHtml(record.failure_id)}</strong>
                  <span class="muted">${escapeHtml(record.timestamp)}</span>
                  <div class="tag-list">
                    <span class="tag ${record.severity === "high" ? "danger" : record.severity === "medium" ? "warning" : "ok"}">${escapeHtml(record.cause_type)}</span>
                    ${record.in_regression ? `<span class="tag ok">in_regression</span>` : `<span class="tag warning">not_in_regression</span>`}
                    ${record.retested_after_fix ? `<span class="tag ok">retested</span>` : ""}
                  </div>
                  <pre>${escapeHtml(JSON.stringify({
                    expected: record.expected,
                    actual: record.actual,
                    artifact_ref: record.artifact_ref,
                  }, null, 2))}</pre>
                </article>
              `,
            )
            .join("")
        : `<div class="empty">当前没有 failure_cases 索引。</div>`}
    </section>
  `;
}

function renderSample(detail) {
  const artifactBlocks = Object.entries(detail.artifacts || {})
    .map(
      ([name, value]) => `
        <article>
          <h3>${escapeHtml(name)}</h3>
          <pre>${escapeHtml(typeof value === "string" ? value : JSON.stringify(value, null, 2))}</pre>
        </article>
      `,
    )
    .join("");
  const runRecord = detail.run_record || {};
  app.innerHTML = `
    <section class="panel">
      <h2>Sample Detail</h2>
      <p>原样回指 artifact，不在页面层做主体语义再解释。</p>
      <div class="tag-list">
        ${Object.entries(runRecord)
          .filter(([key]) => ["bundle_complete", "oe_available", "host_only", "repair_closure"].includes(key))
          .map(([key, value]) => `<span class="tag ${value ? "ok" : "warning"}">${escapeHtml(`${key}=${value}`)}</span>`)
          .join("")}
        ${(runRecord.gap_types || []).map((tag) => `<span class="tag ${gapTag(tag)}">${escapeHtml(tag)}</span>`).join("")}
      </div>
      <pre>${escapeHtml(JSON.stringify(runRecord, null, 2))}</pre>
    </section>
    <section class="detail-grid">${artifactBlocks}</section>
  `;
}

async function refresh() {
  const health = await fetchJson("/api/dashboard/health");
  renderMeta(health.build_meta || {}, health.gap_summary || {});

  if (view === "growth") {
    const growth = await fetchJson("/api/dashboard/growth");
    renderGrowth(growth.records || [], growth.summary || {});
    return;
  }

  if (view === "failures") {
    const failures = await fetchJson("/api/dashboard/failures");
    renderFailures(failures.records || [], failures.gap_summary || {});
    return;
  }

  if (view === "sample" && sampleId) {
    const detail = await fetchJson(`/api/dashboard/samples/${encodeURIComponent(sampleId)}`);
    renderSample(detail);
    return;
  }

  const runs = await fetchJson("/api/dashboard/runs");
  renderRuns(runs.records || [], runs.continuity || []);
}

async function start() {
  try {
    await refresh();
    setInterval(refresh, POLL_MS);
  } catch (error) {
    app.innerHTML = `<section class="panel"><div class="empty">Dashboard load failed: ${escapeHtml(error.message)}</div></section>`;
  }
}

start();
