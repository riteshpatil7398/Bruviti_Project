/**
 * Bruviti Software License Usage & Cost Analytics Dashboard
 * Vanilla JavaScript Single-Page Application Client
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const filterForm = document.getElementById("filterForm");
  const fromInput = document.getElementById("fromDate");
  const toInput = document.getElementById("toDate");
  const orgInput = document.getElementById("orgId");
  const btnSubmit = document.getElementById("btnSubmit");
  const btnReset = document.getElementById("btnReset");

  const errorBanner = document.getElementById("errorBanner");
  const errorTitle = document.getElementById("errorTitle");
  const errorMessage = document.getElementById("errorMessage");
  const closeError = document.getElementById("closeError");

  const loadingIndicator = document.getElementById("loadingIndicator");
  const emptyState = document.getElementById("emptyState");
  const resultsSection = document.getElementById("resultsSection");

  // KPI elements
  const kpiLicensedUsers = document.getElementById("kpiLicensedUsers");
  const kpiActiveUsers = document.getElementById("kpiActiveUsers");
  const kpiEngagementPct = document.getElementById("kpiEngagementPct");
  const engagementFill = document.getElementById("engagementFill");
  const kpiSpend = document.getElementById("kpiSpend");
  const kpiIdleSpend = document.getElementById("kpiIdleSpend");
  const kpiIdlePct = document.getElementById("kpiIdlePct");

  // Table body
  const toolsTableBody = document.getElementById("toolsTableBody");

  // Preset buttons
  const presetButtons = document.querySelectorAll(".btn-chip");

  // Helpers
  function formatCurrency(val) {
    if (val === null || val === undefined || isNaN(val)) return "$0.00";
    return "$" + Number(val).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function formatPct(val) {
    if (val === null || val === undefined || isNaN(val)) return "0.0%";
    return Number(val).toFixed(1) + "%";
  }

  function showError(title, msg) {
    errorTitle.textContent = title;
    errorMessage.textContent = msg;
    errorBanner.style.display = "flex";
  }

  function hideError() {
    errorBanner.style.display = "none";
  }

  closeError.addEventListener("click", hideError);

  function setLoading(isLoading) {
    if (isLoading) {
      hideError();
      loadingIndicator.style.display = "flex";
      emptyState.style.display = "none";
      resultsSection.style.display = "none";
      btnSubmit.disabled = true;
    } else {
      loadingIndicator.style.display = "none";
      btnSubmit.disabled = false;
    }
  }

  // Form submission handler
  async function runAnalysis(e) {
    if (e) e.preventDefault();

    const fromVal = fromInput.value.trim();
    const toVal = toInput.value.trim();
    const orgVal = orgInput.value.trim();

    // Client-side validations
    if (!fromVal || !toVal) {
      showError("Validation Error", "Both 'From Date' and 'To Date' are required.");
      return;
    }

    if (fromVal > toVal) {
      showError("Validation Error", "The 'From Date' must be less than or equal to 'To Date'.");
      return;
    }

    setLoading(true);

    try {
      const queryParams = new URLSearchParams({
        from: fromVal,
        to: toVal
      });
      if (orgVal) {
        queryParams.set("org", orgVal);
      }

      // Concurrently fetch Summary and Tools endpoints
      const [summaryRes, toolsRes] = await Promise.all([
        fetch(`/api/summary?${queryParams.toString()}`),
        fetch(`/api/tools?${queryParams.toString()}`)
      ]);

      if (!summaryRes.ok) {
        const errorData = await summaryRes.json().catch(() => ({}));
        throw new Error(errorData.detail || `Summary API returned HTTP ${summaryRes.status}`);
      }

      if (!toolsRes.ok) {
        const errorData = await toolsRes.json().catch(() => ({}));
        throw new Error(errorData.detail || `Tools API returned HTTP ${toolsRes.status}`);
      }

      const summary = await summaryRes.json();
      const tools = await toolsRes.json();

      renderSummary(summary);
      renderTools(tools);

      emptyState.style.display = "none";
      resultsSection.style.display = "block";
    } catch (err) {
      showError("Analysis Failed", err.message || "An unexpected error occurred while fetching metrics.");
      emptyState.style.display = "block";
      resultsSection.style.display = "none";
    } finally {
      setLoading(false);
    }
  }

  function renderSummary(summary) {
    kpiLicensedUsers.textContent = (summary.licensed_users ?? 0).toLocaleString();
    kpiActiveUsers.textContent = (summary.active_users ?? 0).toLocaleString();

    const engPct = summary.engagement_pct ?? 0.0;
    kpiEngagementPct.textContent = formatPct(engPct);
    engagementFill.style.width = Math.min(Math.max(engPct, 0), 100) + "%";

    const spend = summary.spend ?? 0.0;
    const idleSpend = summary.idle_spend ?? 0.0;
    kpiSpend.textContent = formatCurrency(spend);
    kpiIdleSpend.textContent = formatCurrency(idleSpend);

    if (spend > 0) {
      const idleRatio = ((idleSpend / spend) * 100).toFixed(1);
      kpiIdlePct.textContent = `${idleRatio}% of total spend is unutilized`;
    } else {
      kpiIdlePct.textContent = "No spend in selected window";
    }
  }

  function renderTools(tools) {
    toolsTableBody.innerHTML = "";

    if (!Array.isArray(tools) || tools.length === 0) {
      toolsTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 20px;">No tools data available</td></tr>`;
      return;
    }

    tools.forEach((t) => {
      const tr = document.createElement("tr");

      const eng = t.engagement_pct ?? 0.0;
      let badgeClass = "badge-pct-low";
      if (eng >= 70) badgeClass = "badge-pct-high";
      else if (eng >= 40) badgeClass = "badge-pct-med";

      const costPerActiveText = t.cost_per_active !== null && t.cost_per_active !== undefined
        ? formatCurrency(t.cost_per_active)
        : '<span style="color: var(--text-muted);">—</span>';

      tr.innerHTML = `
        <td class="tool-name-badge">${escapeHtml(t.tool)}</td>
        <td>${Number(t.licensed_users ?? 0).toLocaleString()}</td>
        <td>${Number(t.active_users ?? 0).toLocaleString()}</td>
        <td><span class="badge-pct ${badgeClass}">${formatPct(eng)}</span></td>
        <td>${formatCurrency(t.spend)}</td>
        <td class="${t.idle_spend > 0 ? 'text-warning' : ''}">${formatCurrency(t.idle_spend)}</td>
        <td>${costPerActiveText}</td>
      `;

      toolsTableBody.appendChild(tr);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Preset button click
  presetButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      fromInput.value = btn.dataset.from;
      toInput.value = btn.dataset.to;
      runAnalysis();
    });
  });

  // Reset button click
  btnReset.addEventListener("click", () => {
    fromInput.value = "2026-01-01";
    toInput.value = "2026-09-30";
    orgInput.value = "";
    hideError();
    emptyState.style.display = "block";
    resultsSection.style.display = "none";
  });

  filterForm.addEventListener("submit", runAnalysis);

  // Automatically execute analysis on initial page load
  runAnalysis();
});
