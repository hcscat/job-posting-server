function splitLines(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
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

async function refreshDashboardRuns() {
  const tbody = document.getElementById("recent-runs-body");
  if (!tbody) return;
  const response = await fetch("/api/runs?limit=8");
  const runs = await response.json();
  tbody.innerHTML = runs
    .map(
      (run) => `
      <tr>
        <td>${run.id}</td>
        <td>${run.started_at}</td>
        <td><span class="pill ${run.status}">${run.status}</span></td>
        <td>${run.triggered_by}</td>
        <td>${run.saved_count}</td>
        <td>${run.message}</td>
      </tr>`
    )
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const settingsForm = document.getElementById("settings-form");
  if (settingsForm) {
    const settings = JSON.parse(settingsForm.dataset.settings);

    document
      .querySelectorAll('input[name="site_keys"]')
      .forEach((input) => (input.checked = settings.site_keys.includes(input.value)));

    [
      "queries",
      "roles",
      "keywords",
      "exclude_keywords",
      "locations",
      "companies",
      "experience_levels",
      "education_levels",
      "employment_types",
      "required_terms",
      "extra_terms",
      "strict_match_groups",
      "user_agent",
      "output_dir",
      "max_results_per_site",
      "request_timeout_seconds",
      "concurrency",
      "pause_between_searches_seconds",
      "schedule_enabled",
      "schedule_mode",
      "schedule_times",
      "schedule_interval_hours",
      "schedule_run_on_start",
      "schedule_timezone",
      "fetch_details",
      "store_html",
    ].forEach((id) => setFieldValue(id, settings[id]));

    settingsForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = document.getElementById("settings-status");
      const payload = {
        site_keys: Array.from(document.querySelectorAll('input[name="site_keys"]:checked')).map((item) => item.value),
        queries: splitLines(document.getElementById("queries").value),
        roles: splitLines(document.getElementById("roles").value),
        keywords: splitLines(document.getElementById("keywords").value),
        exclude_keywords: splitLines(document.getElementById("exclude_keywords").value),
        locations: splitLines(document.getElementById("locations").value),
        companies: splitLines(document.getElementById("companies").value),
        experience_levels: splitLines(document.getElementById("experience_levels").value),
        education_levels: splitLines(document.getElementById("education_levels").value),
        employment_types: splitLines(document.getElementById("employment_types").value),
        required_terms: splitLines(document.getElementById("required_terms").value),
        extra_terms: splitLines(document.getElementById("extra_terms").value),
        strict_match_groups: splitLines(document.getElementById("strict_match_groups").value),
        max_results_per_site: Number(document.getElementById("max_results_per_site").value || 8),
        request_timeout_seconds: Number(document.getElementById("request_timeout_seconds").value || 20),
        fetch_details: document.getElementById("fetch_details").checked,
        store_html: document.getElementById("store_html").checked,
        concurrency: Number(document.getElementById("concurrency").value || 4),
        pause_between_searches_seconds: Number(document.getElementById("pause_between_searches_seconds").value || 1),
        user_agent: document.getElementById("user_agent").value.trim(),
        output_dir: document.getElementById("output_dir").value.trim() || "./data/exports",
        schedule_enabled: document.getElementById("schedule_enabled").checked,
        schedule_mode: document.getElementById("schedule_mode").value,
        schedule_times: splitLines(document.getElementById("schedule_times").value),
        schedule_interval_hours: Number(document.getElementById("schedule_interval_hours").value || 4),
        schedule_run_on_start: document.getElementById("schedule_run_on_start").checked,
        schedule_timezone: document.getElementById("schedule_timezone").value.trim() || "Asia/Seoul",
      };

      status.textContent = "저장 중...";
      const response = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        status.textContent = error.detail || "저장 실패";
        return;
      }

      status.textContent = "저장 완료";
    });
  }

  const runButton = document.getElementById("run-now-button");
  if (runButton) {
    runButton.addEventListener("click", async () => {
      runButton.disabled = true;
      runButton.textContent = "수집 중...";
      const response = await fetch("/api/collect", { method: "POST" });
      if (!response.ok) {
        const error = await response.json();
        alert(error.detail || "수집 실행 실패");
      } else {
        await refreshDashboardRuns();
      }
      runButton.disabled = false;
      runButton.textContent = "지금 수집";
    });
  }
});
