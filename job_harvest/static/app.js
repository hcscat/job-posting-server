const APP_MESSAGES = (() => {
  try {
    return JSON.parse(document.body?.dataset.messages || "{}");
  } catch (_error) {
    return {};
  }
})();

const APP_SITE_LABELS = (() => {
  try {
    return JSON.parse(document.body?.dataset.siteLabels || "{}");
  } catch (_error) {
    return {};
  }
})();

function t(key, replacements = {}) {
  const template = APP_MESSAGES[key] || key;
  return Object.entries(replacements).reduce(
    (result, [name, value]) => result.replaceAll(`{${name}}`, String(value)),
    template
  );
}

function splitLines(value) {
  return value
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function decodeHtmlEntities(value) {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = String(value ?? "");
  return textarea.value;
}

function normalizeDisplayText(value) {
  return decodeHtmlEntities(value)
    .replaceAll("\r\n", "\n")
    .replaceAll("\r", "\n")
    .replaceAll("\u00a0", " ")
    .trim();
}

// Normalize section headings and bullets so mixed-source detail text stays readable in the drawer.
function formatNormalizedJobDescription(value) {
  const source = normalizeDisplayText(value);
  if (!source) {
    return t("common.not_available");
  }

  const headings = [
    "주요 업무",
    "주요업무",
    "자격 요건",
    "자격요건",
    "우대 사항",
    "우대사항",
    "복지",
    "혜택",
    "기술 스택",
    "기술스택",
    "지원 방법",
    "채용 절차",
    "전형 절차",
    "Introduction",
    "Description",
    "Primary Responsibility",
    "Primary Responsibilities",
    "Responsibilities",
    "Required Qualification",
    "Required Qualifications",
    "Requirements",
    "Qualifications",
    "Preferred Skill",
    "Preferred Skills",
    "Preferred",
    "Preferred Qualification",
    "Preferred Qualifications",
    "Benefits",
    "Hiring Process",
    "Tech Stack",
    "Location",
    "Locations",
  ];

  let normalized = source
    .replace(/([•·▪■])\s*/g, "\n- ")
    .replace(/(?<!\n)(\d+\.)\s+/g, "\n$1 ")
    .replace(/\n{3,}/g, "\n\n");

  headings.forEach((heading) => {
    const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    normalized = normalized.replace(
      new RegExp(`\\s*(${escaped})(\\s*[:|])\\s*`, "g"),
      `\n\n$1$2\n`
    );
  });

  const rawLines = normalized.split("\n");
  const lines = [];
  const sectionHeading =
    /^(Introduction|Description|Primary Responsibility|Primary Responsibilities|Responsibilities|Required Qualification|Required Qualifications|Requirements|Qualifications|Preferred Skill|Preferred Skills|Preferred|Preferred Qualification|Preferred Qualifications|Benefits|Hiring Process|Tech Stack|Location|Locations|주요 업무|주요업무|자격 요건|자격요건|우대 사항|우대사항|복지|혜택|기술 스택|기술스택|지원 방법|채용 절차|전형 절차)(\s*:?|\s*)$/i;

  rawLines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      if (lines[lines.length - 1] !== "") {
        lines.push("");
      }
      return;
    }
    if (sectionHeading.test(trimmed) && lines.length && lines[lines.length - 1] !== "") {
      lines.push("");
    }
    lines.push(trimmed);
  });

  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function buildDescriptionText(job) {
  // When detail fetch falls back to listing data, prefer the best available summary text.
  return normalizeDisplayText(job.description || job.ai_summary || job.summary || "");
}

function siteLabel(siteKey, fallback = "") {
  if (!siteKey) return fallback || t("common.not_available");
  return APP_SITE_LABELS[siteKey] || fallback || siteKey;
}

function setFieldValue(id, value) {
  const element = document.getElementById(id);
  if (!element) return;
  if (element.type === "checkbox") {
    element.checked = Boolean(value);
    return;
  }
  if (Array.isArray(value)) {
    element.value = value.join("\n");
    return;
  }
  element.value = value ?? "";
}

function setSiteSelections(siteKeys) {
  const selected = new Set(siteKeys || []);
  document.querySelectorAll('input[name="site_keys"]').forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

const SETTINGS_FIELD_IDS = [
  "queries",
  "crawl_strategy",
  "crawl_terms",
  "listing_page_limit",
  "roles",
  "keywords",
  "exclude_keywords",
  "locations",
  "companies",
  "experience_levels",
  "education_levels",
  "employment_types",
  "required_terms",
  "industries",
  "salary_ranges",
  "company_types",
  "company_sizes",
  "position_levels",
  "majors",
  "certifications",
  "preferred_conditions",
  "welfare",
  "skills",
  "tags",
  "workplace_types",
  "date_posted",
  "deadline",
  "easy_apply",
  "applicant_signals",
  "network_signals",
  "leader_positions",
  "headhunting",
  "theme_tags",
  "extra_terms",
  "strict_match_groups",
  "user_agent",
  "output_dir",
  "max_results_per_site",
  "request_timeout_seconds",
  "detail_refetch_hours",
  "concurrency",
  "pause_between_searches_seconds",
  "ai_enrichment_enabled",
  "ai_provider",
  "ai_model",
  "fetch_details",
  "store_html",
  "browser_enabled",
  "browser_headless",
  "browser_timeout_seconds",
];

function applySettingsPayload(settings) {
  if (!settings) return;
  setSiteSelections(settings.site_keys || []);
  SETTINGS_FIELD_IDS.forEach((id) => setFieldValue(id, settings[id]));
}

function collectSettingsPayload() {
  return {
    site_keys: Array.from(document.querySelectorAll('input[name="site_keys"]:checked')).map((item) => item.value),
    queries: splitLines(document.getElementById("queries").value),
    crawl_strategy: document.getElementById("crawl_strategy").value,
    crawl_terms: splitLines(document.getElementById("crawl_terms").value),
    listing_page_limit: Number(document.getElementById("listing_page_limit").value || 0),
    roles: splitLines(document.getElementById("roles").value),
    keywords: splitLines(document.getElementById("keywords").value),
    exclude_keywords: splitLines(document.getElementById("exclude_keywords").value),
    locations: splitLines(document.getElementById("locations").value),
    companies: splitLines(document.getElementById("companies").value),
    experience_levels: splitLines(document.getElementById("experience_levels").value),
    education_levels: splitLines(document.getElementById("education_levels").value),
    employment_types: splitLines(document.getElementById("employment_types").value),
    required_terms: splitLines(document.getElementById("required_terms").value),
    industries: splitLines(document.getElementById("industries").value),
    salary_ranges: splitLines(document.getElementById("salary_ranges").value),
    company_types: splitLines(document.getElementById("company_types").value),
    company_sizes: splitLines(document.getElementById("company_sizes").value),
    position_levels: splitLines(document.getElementById("position_levels").value),
    majors: splitLines(document.getElementById("majors").value),
    certifications: splitLines(document.getElementById("certifications").value),
    preferred_conditions: splitLines(document.getElementById("preferred_conditions").value),
    welfare: splitLines(document.getElementById("welfare").value),
    skills: splitLines(document.getElementById("skills").value),
    tags: splitLines(document.getElementById("tags").value),
    workplace_types: splitLines(document.getElementById("workplace_types").value),
    date_posted: splitLines(document.getElementById("date_posted").value),
    deadline: splitLines(document.getElementById("deadline").value),
    easy_apply: splitLines(document.getElementById("easy_apply").value),
    applicant_signals: splitLines(document.getElementById("applicant_signals").value),
    network_signals: splitLines(document.getElementById("network_signals").value),
    leader_positions: splitLines(document.getElementById("leader_positions").value),
    headhunting: splitLines(document.getElementById("headhunting").value),
    theme_tags: splitLines(document.getElementById("theme_tags").value),
    extra_terms: splitLines(document.getElementById("extra_terms").value),
    strict_match_groups: splitLines(document.getElementById("strict_match_groups").value),
    max_results_per_site: Number(document.getElementById("max_results_per_site").value || 8),
    request_timeout_seconds: Number(document.getElementById("request_timeout_seconds").value || 20),
    fetch_details: document.getElementById("fetch_details").checked,
    store_html: document.getElementById("store_html").checked,
    detail_refetch_hours: Number(document.getElementById("detail_refetch_hours").value || 24),
    concurrency: Number(document.getElementById("concurrency").value || 4),
    pause_between_searches_seconds: Number(document.getElementById("pause_between_searches_seconds").value || 1),
    ai_enrichment_enabled: document.getElementById("ai_enrichment_enabled").checked,
    ai_provider: document.getElementById("ai_provider").value,
    ai_model: document.getElementById("ai_model").value.trim(),
    user_agent: document.getElementById("user_agent").value.trim(),
    browser_enabled: document.getElementById("browser_enabled").checked,
    browser_headless: document.getElementById("browser_headless").checked,
    browser_timeout_seconds: Number(document.getElementById("browser_timeout_seconds").value || 60),
    output_dir: document.getElementById("output_dir").value.trim() || "./data/exports",
  };
}

function createListMarkup(values) {
  const items = Array.isArray(values)
    ? values.map((value) => normalizeDisplayText(value)).filter(Boolean)
    : [];
  if (!items.length) {
    return `<li>${escapeHtml(t("common.not_available"))}</li>`;
  }
  return items.map((value) => `<li>${escapeHtml(value)}</li>`).join("");
}

function createChipMarkup(values) {
  const items = Array.isArray(values)
    ? values.map((value) => normalizeDisplayText(value)).filter(Boolean)
    : [];
  if (!items.length) {
    return `<span class="subtle">${escapeHtml(t("common.not_available"))}</span>`;
  }
  return items.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("");
}

function createSnapshotValue(category, sha256Hex) {
  if (!sha256Hex) {
    return escapeHtml(t("common.not_available"));
  }
  return `<a href="/raw/${category}/${encodeURIComponent(sha256Hex)}">${escapeHtml(t("common.view"))}</a>`;
}

function translateJobFamily(value) {
  if (!value) return t("common.not_available");
  const key = `job_family.${value}`;
  const translated = t(key);
  return translated === key ? value : translated;
}

function formatJobDescription(value) {
  const source = String(value || "")
    .replaceAll("\r\n", "\n")
    .replaceAll("\r", "\n")
    .replaceAll("\u00a0", " ")
    .trim();
  if (!source) {
    return t("common.not_available");
  }

  const headings = [
    "주요업무",
    "자격요건",
    "지원자격",
    "우대사항",
    "복지",
    "혜택",
    "기술스택",
    "기술 스택",
    "지원 방법",
    "채용 절차",
    "전형 절차",
    "Introduction",
    "Description",
    "Primary Responsibility",
    "Primary Responsibilities",
    "Required Qualification",
    "Requirements",
    "Qualifications",
    "Preferred Skill",
    "Preferred",
    "Benefits",
    "Hiring Process",
    "Tech Stack",
    "Locations",
  ];

  let normalized = source
    .replace(/\s([•▪■◆▶▷○●])\s*/g, "\n$1 ")
    .replace(/(?<!\n)(\d+\.)\s+/g, "\n$1 ")
    .replace(/\n{3,}/g, "\n\n");

  headings.forEach((heading) => {
    const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    normalized = normalized.replace(
      new RegExp(`\\s*(${escaped}\\s*[:：]?)\\s*`, "g"),
      `\n\n$1\n`
    );
  });

  const rawLines = normalized.split("\n");
  const lines = [];
  const sectionHeading =
    /^(Introduction|Description|Primary Responsibility|Primary Responsibilities|Required Qualification|Requirements|Qualifications|Preferred Skill|Preferred|Benefits|Hiring Process|Tech Stack|Locations|주요업무|자격요건|지원자격|우대사항|복지|혜택|기술스택|기술 스택|지원 방법|채용 절차|전형 절차)(\s*:?|\s*)$/i;

  rawLines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      if (lines[lines.length - 1] !== "") {
        lines.push("");
      }
      return;
    }
    if (sectionHeading.test(trimmed) && lines.length && lines[lines.length - 1] !== "") {
      lines.push("");
    }
    lines.push(trimmed);
  });

  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function createMetadataMarkup(job) {
  const rows = [
    ["common.site", siteLabel(job.site_key, job.site_name || "")],
    ["common.company", job.company || t("common.not_available")],
    ["common.location", job.location || t("common.not_available")],
    ["common.employment", job.employment_type || t("common.not_available")],
    ["common.experience", job.experience_level || t("common.not_available")],
    ["common.education", job.education_level || t("common.not_available")],
    ["common.job_family", translateJobFamily(job.ai_job_family)],
    ["common.seniority", job.ai_seniority || t("common.not_available")],
    ["common.work_model", job.ai_work_model || t("common.not_available")],
  ];
  return rows
    .map(
      ([labelKey, value]) =>
        `<dt>${escapeHtml(t(labelKey))}</dt><dd>${escapeHtml(value)}</dd>`
    )
    .join("");
}

function createSnapshotMarkup(job) {
  const rows = [
    ["jobs.listing_raw", createSnapshotValue("listing", job.listing_snapshot_sha256)],
    ["jobs.detail_raw", createSnapshotValue("detail", job.detail_snapshot_sha256)],
  ];
  return rows
    .map(
      ([labelKey, value]) =>
        `<dt>${escapeHtml(t(labelKey))}</dt><dd>${value}</dd>`
    )
    .join("");
}

async function openJobDetail(jobId) {
  const drawer = document.getElementById("job-detail-drawer");
  const inlineRow = document.getElementById("job-detail-row");
  if (!drawer || !inlineRow) return;

  const trigger = document.querySelector(`.detail-trigger[data-job-id="${CSS.escape(String(jobId))}"]`);
  const row = trigger?.closest("tr");
  if (!row) return;

  if (inlineRow.dataset.jobId === String(jobId) && !inlineRow.classList.contains("is-hidden")) {
    closeJobDetail();
    return;
  }

  inlineRow.dataset.jobId = String(jobId);
  row.insertAdjacentElement("afterend", inlineRow);
  inlineRow.classList.remove("is-hidden");

  document.querySelectorAll(".detail-trigger[aria-expanded='true']").forEach((button) => {
    button.setAttribute("aria-expanded", "false");
  });
  trigger?.setAttribute("aria-expanded", "true");

  const title = document.getElementById("job-detail-title");
  const status = document.getElementById("job-detail-status");
  const content = document.getElementById("job-detail-content");
  const external = document.getElementById("job-detail-external");

  drawer.classList.remove("is-hidden");
  content.classList.add("is-hidden");
  external.classList.add("is-hidden");
  title.textContent = t("jobs.drawer_title");
  status.textContent = t("js.jobs.loading");
  status.classList.remove("is-hidden");
  inlineRow.scrollIntoView({ behavior: "smooth", block: "nearest" });

  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    status.textContent = t("js.jobs.failed");
    return;
  }

  const job = await response.json();
  title.textContent = job.title || job.search_title || t("jobs.drawer_title");
  document.getElementById("job-detail-metadata").innerHTML = createMetadataMarkup(job);
  document.getElementById("job-detail-summary").textContent =
    normalizeDisplayText(job.ai_summary || job.summary || t("jobs.summary_empty"));
  document.getElementById("job-detail-tech-stack").innerHTML = createChipMarkup(job.ai_tech_stack);
  document.getElementById("job-detail-requirements").innerHTML = createListMarkup(job.ai_requirements);
  document.getElementById("job-detail-responsibilities").innerHTML = createListMarkup(job.ai_responsibilities);
  document.getElementById("job-detail-benefits").innerHTML = createListMarkup(job.ai_benefits);
  document.getElementById("job-detail-snapshots").innerHTML = createSnapshotMarkup(job);
  document.getElementById("job-detail-description").textContent = formatNormalizedJobDescription(buildDescriptionText(job));
  document.getElementById("job-detail-raw-payload").textContent = JSON.stringify(job.raw_payload || {}, null, 2);

  if (job.url) {
    external.href = job.url;
    external.classList.remove("is-hidden");
  }

  status.classList.add("is-hidden");
  content.classList.remove("is-hidden");
}

function closeJobDetail() {
  const drawer = document.getElementById("job-detail-drawer");
  const inlineRow = document.getElementById("job-detail-row");
  const content = document.getElementById("job-detail-content");
  const status = document.getElementById("job-detail-status");
  const external = document.getElementById("job-detail-external");
  if (!drawer || !inlineRow) return;

  drawer.classList.add("is-hidden");
  content?.classList.add("is-hidden");
  status?.classList.remove("is-hidden");
  if (external) {
    external.classList.add("is-hidden");
    external.removeAttribute("href");
  }
  inlineRow.classList.add("is-hidden");
  inlineRow.dataset.jobId = "";
  document.querySelectorAll(".detail-trigger[aria-expanded='true']").forEach((button) => {
    button.setAttribute("aria-expanded", "false");
  });
}

function bindSettingsPage() {
  const settingsForm = document.getElementById("settings-form");
  if (!settingsForm) return;

  const settings = JSON.parse(settingsForm.dataset.settings);
  applySettingsPayload(settings);

  const interpretButton = document.getElementById("interpret-request-button");
  if (interpretButton) {
    interpretButton.addEventListener("click", async () => {
      const requestField = document.getElementById("interpret_request");
      const status = document.getElementById("interpret-status");
      const notes = document.getElementById("interpret-notes");
      const text = requestField.value.trim();
      if (!text) {
        status.textContent = t("js.settings.enter_request");
        return;
      }

      interpretButton.disabled = true;
      status.textContent = t("js.settings.interpreting");
      notes.textContent = "";

      const response = await fetch("/api/settings/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          base_payload: collectSettingsPayload(),
        }),
      });

      interpretButton.disabled = false;
      if (!response.ok) {
        const error = await response.json();
        status.textContent = error.detail || t("js.settings.interpret_failed");
        return;
      }

      const result = await response.json();
      applySettingsPayload(result.payload);
      status.textContent = t("js.settings.interpret_applied", {
        provider: result.provider,
        model: result.model,
      });
      notes.textContent = (result.notes || []).join(" ");
    });
  }

  settingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("settings-status");
    const payload = collectSettingsPayload();

    status.textContent = t("js.settings.saving");
    const response = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      status.textContent = error.detail || t("js.settings.save_failed");
      return;
    }

    settingsForm.dataset.settings = JSON.stringify(payload);
    status.textContent = t("js.settings.saved");
  });
}

function bindJobsPage() {
  const drawer = document.getElementById("job-detail-drawer");
  if (!drawer) return;

  document.querySelectorAll(".detail-trigger").forEach((button) => {
    button.addEventListener("click", async () => {
      await openJobDetail(button.dataset.jobId);
    });
  });

  const closeButton = document.getElementById("job-detail-close");
  if (closeButton) {
    closeButton.addEventListener("click", closeJobDetail);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindSettingsPage();
  bindJobsPage();
});
