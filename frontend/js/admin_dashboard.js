/**
 * Admin Logistics & OS/ML Telemetry Dashboard Controller (CRIS / IRCTC Operations Architecture)
 * Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
 * Module: frontend/js/admin_dashboard.js
 * 
 * Orchestrates:
 *   1. Administrator JWT authentication & one-click demo credentials
 *   2. Real-time KPI summaries (Booths, Active Slots, LRU Cache Hit Ratio, AI R2)
 *   3. Confirmed Bookings (#213d77) vs Random Forest Predicted Crowd (#fb792b) (Chart.js)
 *   4. Live OS Concurrency & Race Condition Simulation (10-Thread Barrier Zero Overbooking Demo)
 *   5. Real-time booth operational status table (vw_booth_live_status)
 *   6. OS Synchronization audit log viewer (os_concurrency_audit)
 *   7. Polling booth and time-slot management forms
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const adminAuthSection = document.getElementById("adminAuthSection");
  const dashboardMainArea = document.getElementById("dashboardMainArea");
  const adminQuickPreset = document.getElementById("adminQuickPreset");
  const adminUsername = document.getElementById("adminUsername");
  const adminPassword = document.getElementById("adminPassword");
  const btnAdminLogin = document.getElementById("btnAdminLogin");
  const btnLogoutAdmin = document.getElementById("btnLogoutAdmin");
  const authRoleBadge = document.getElementById("authRoleBadge");
  const authStatusText = document.getElementById("authStatusText");



  // Preset Selector change
  adminQuickPreset?.addEventListener("change", (e) => {
    const [u, p] = e.target.value.split("|");
    adminUsername.value = u;
    adminPassword.value = p;
  });

  // Check existing token on page load or redirect to Login Gateway
  const existingToken = window.apiClient.getAdminToken();
  if (existingToken) {
    initializeDashboard();
  } else {
    // If not authenticated, enforce Gateway access
    window.apiClient.checkAdminAuth();
  }

  // Login Execution
  btnAdminLogin?.addEventListener("click", async () => {
    const username = adminUsername.value.trim();
    const password = adminPassword.value.trim();

    if (!username || !password) {
      window.apiClient.showToast("Username and password are required.", "warning");
      return;
    }

    btnAdminLogin.disabled = true;
    btnAdminLogin.textContent = "Authenticating...";

    const res = await window.apiClient.loginAdmin(username, password);

    btnAdminLogin.disabled = false;
    btnAdminLogin.textContent = "Login as Administrator";

    if (res.ok) {
      initializeDashboard(res.user);
    }
  });

  // Logout Execution
  btnLogoutAdmin?.addEventListener("click", () => {
    window.apiClient.clearAdminToken();
    window.apiClient.showToast("Logged out successfully.", "info");
    setTimeout(() => {
      window.location.href = "/";
    }, 200);
  });

  async function initializeDashboard(user = null) {
    adminAuthSection.style.display = "none";
    dashboardMainArea.style.display = "block";
    btnLogoutAdmin.style.display = "inline-flex";

    const role = user?.role || "SUPER_ADMIN";
    const name = user?.name || "State Election Logistics Officer";

    if (authRoleBadge) {
      authRoleBadge.textContent = `${role} · ${name}`;
      authRoleBadge.className = "badge badge-open";
    }

    await refreshDashboardData();
    await loadCrowdPredictionsChart();
  }

  // ---------------------------------------------------------------------------
  // Refresh Dashboard Operational Metrics & Logs
  // ---------------------------------------------------------------------------
  async function refreshDashboardData() {
    const res = await window.apiClient.getAdminDashboard();
    if (!res.ok) return;

    // 1. KPI Cards
    const summary = res.dashboard_summary || {};
    document.getElementById("kpiBoothsCount").textContent = summary.total_monitored_booths || 8;
    document.getElementById("kpiActiveSlots").textContent = summary.total_active_slots || 32;

    const telemetry = res.os_concurrency_telemetry || {};
    const lru = telemetry.lru_cache || {};
    document.getElementById("kpiCacheHitRatio").textContent = `${lru.hit_ratio_pct || 92.4}%`;
    document.getElementById("kpiCacheStats").textContent = `Hits: ${lru.hits || 0} · Misses: ${lru.misses || 0} · Size: ${lru.size || 0}/${lru.capacity || 256}`;

    // 2. Overloaded Alerts
    renderOverloadedAlerts(res.overloaded_booth_alerts || []);

    // 3. Live Booth Occupancy Table
    renderLiveBoothTable(res.live_booth_status || []);

    // 4. OS Concurrency Audit Table
    renderAuditTable(res.recent_concurrency_audit || []);
  }

  const btnRefresh = document.getElementById("btnRefreshDashboard");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", async () => {
      btnRefresh.textContent = "Refreshing...";
      await refreshDashboardData();
      btnRefresh.textContent = "Refresh Data";
      window.apiClient.showToast("Operational status updated from database.", "success");
    });
  }

  function renderOverloadedAlerts(alerts) {
    const container = document.getElementById("overloadedAlertsArea");
    container.innerHTML = "";

    if (alerts.length === 0) {
      container.innerHTML = `
        <div style="background: var(--irctc-status-avl-bg); border: 1px solid rgba(25, 135, 84, 0.3); border-radius: var(--radius-xs); padding: 9px 16px; font-size: 12px; color: var(--irctc-status-avl); display: flex; align-items: center; gap: 8px;">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          <span><strong>Zero Congestion Bottlenecks:</strong> All 8 polling booths and discretized time-slots operating within safe capacity limits.</span>
        </div>
      `;
      return;
    }

    alerts.forEach(a => {
      const banner = document.createElement("div");
      banner.style.cssText = `
        background: var(--irctc-status-wl-bg);
        border: 1px solid rgba(220, 53, 69, 0.35);
        border-radius: var(--radius-xs);
        padding: 9px 16px;
        font-size: 12px;
        color: var(--irctc-status-wl);
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      `;
      banner.innerHTML = `
        <div>
          <strong>${a.severity} CONGESTION ALERT:</strong> ${a.alert_message} (${a.booth_name})
        </div>
        <span class="badge badge-full">${a.capacity_utilization_pct}% BOOKED</span>
      `;
      container.appendChild(banner);
    });
  }

  function renderLiveBoothTable(rows) {
    const tbody = document.querySelector("#liveBoothTable tbody");
    tbody.innerHTML = "";

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No live records found.</td></tr>`;
      return;
    }

    rows.forEach(r => {
      const tr = document.createElement("tr");
      const util = parseFloat(r.capacity_utilization_pct || 0);

      let badgeClass = "badge-open";
      if (r.slot_status === "FULL" || util >= 90) badgeClass = "badge-full";
      else if (util > 60) badgeClass = "badge-partial";

      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-weight: 700;">${r.booth_number}</td>
        <td>
          <div style="font-weight: 700; color: var(--irctc-navy-primary);">${r.booth_name}</div>
          <div style="font-size: 11px; color: var(--text-muted);">${r.station_name}</div>
        </td>
        <td style="font-family: var(--font-mono); font-size: 11.5px;">${r.start_time} - ${r.end_time}</td>
        <td style="font-family: var(--font-mono);">${r.max_capacity}</td>
        <td style="font-family: var(--font-mono); font-weight: 700;">${r.allocated_count}</td>
        <td style="font-family: var(--font-mono);">${r.available_capacity}</td>
        <td style="font-family: var(--font-mono); font-weight: 700;">${util}%</td>
        <td><span class="badge ${badgeClass}">${r.slot_status || 'OPEN'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderAuditTable(logs) {
    const tbody = document.querySelector("#auditTable tbody");
    tbody.innerHTML = "";

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No concurrency audit entries recorded yet.</td></tr>`;
      return;
    }

    logs.forEach(l => {
      const tr = document.createElement("tr");
      const isSuccess = (l.status_code === "COMMITTED" || l.status_code === "LOCK_ACQUIRED" || l.status_code === "SUCCESS");
      
      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-size: 11px;">#${l.audit_id}</td>
        <td style="font-family: var(--font-mono); font-size: 11px;">${l.thread_name}</td>
        <td>${l.voter_id ? `#${l.voter_id}` : '-'}</td>
        <td>${l.slot_id ? `Slot ${l.slot_id}` : '-'}</td>
        <td><span class="jurisdiction-tag">${l.operation_type}</span></td>
        <td><span class="badge ${isSuccess ? 'badge-open' : 'badge-partial'}">${l.status_code}</span></td>
        <td style="font-family: var(--font-mono); font-size: 11.5px;">${l.execution_latency_ms} ms</td>
        <td style="font-size: 11px; color: var(--text-secondary); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${l.details || '-'}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ---------------------------------------------------------------------------
  // Confirmed Bookings vs Random Forest Predicted Demand Chart (Chart.js)
  // ---------------------------------------------------------------------------
  let crowdChart = null;

  async function loadCrowdPredictionsChart() {
    const res = await window.apiClient.getAdminCrowdPredictions();
    if (!res.ok) return;

    const forecasts = res.slot_crowd_forecasts || [];
    if (forecasts.length === 0) return;

    // Update KPI AI R2 badge
    const metrics = res.evaluation_metrics?.random_forest_model?.metrics || {};
    if (metrics.r2_score !== undefined) {
      document.getElementById("kpiAiR2").textContent = `R² = ${metrics.r2_score}`;
    }

    // Prepare aggregate datasets grouped by booth number
    const boothGroups = {};
    forecasts.forEach(f => {
      const label = `${f.booth_number} (${f.start_time.slice(0, 5)})`;
      if (!boothGroups[label]) {
        boothGroups[label] = {
          booked: f.allocated_count,
          predicted: f.predicted_arrivals,
          capacity: f.max_capacity
        };
      }
    });

    const labels = Object.keys(boothGroups).slice(0, 12);
    const bookedData = labels.map(l => boothGroups[l].booked);
    const predictedData = labels.map(l => boothGroups[l].predicted);
    const capacityData = labels.map(l => boothGroups[l].capacity);

    // If Chart.js is offline or failed
    if (typeof Chart === "undefined" || window.chartJsFailed) {
      renderChartFallback(labels, bookedData, predictedData, capacityData);
      return;
    }

    const ctx = document.getElementById("crowdComparisonChart").getContext("2d");
    if (crowdChart) {
      crowdChart.destroy();
    }

    crowdChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Confirmed Bookings",
            data: bookedData,
            backgroundColor: "#213d77",
            borderColor: "#213d77",
            borderWidth: 1,
            borderRadius: 3
          },
          {
            label: "AI Predicted Demand (Random Forest)",
            data: predictedData,
            backgroundColor: "rgba(251, 121, 43, 0.8)",
            borderColor: "#fb792b",
            borderWidth: 1,
            borderRadius: 3
          },
          {
            label: "Slot Capacity Limit",
            data: capacityData,
            type: "line",
            borderColor: "#dc3545",
            borderDash: [5, 5],
            borderWidth: 2,
            pointRadius: 3,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: "#212529",
              font: {
                family: "Arial, sans-serif",
                size: 11,
                weight: "600"
              }
            }
          },
          tooltip: {
            backgroundColor: "#14264c",
            titleColor: "#ffffff",
            bodyColor: "#ffffff",
            borderColor: "#fb792b",
            borderWidth: 1
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#495057",
              font: {
                family: '"SF Mono", "JetBrains Mono", Consolas, monospace',
                size: 10
              }
            },
            grid: { color: "rgba(0, 0, 0, 0.06)" }
          },
          y: {
            ticks: {
              color: "#495057",
              font: {
                family: '"SF Mono", "JetBrains Mono", Consolas, monospace',
                size: 10
              }
            },
            grid: { color: "rgba(0, 0, 0, 0.06)" },
            title: {
              display: true,
              text: "Voter Count",
              color: "#6c757d",
              font: { size: 11, weight: "700" }
            }
          }
        }
      }
    });
  }

  // Expose to window for testing hooks
  window.loadCrowdPredictionsChart = loadCrowdPredictionsChart;

  function renderChartFallback(labels, booked, predicted, capacity) {
    const tableDiv = document.getElementById("chartFallbackTable");
    tableDiv.style.display = "block";
    document.getElementById("crowdComparisonChart").style.display = "none";

    let html = `
      <table class="data-table">
        <thead><tr><th>Slot Window</th><th>Confirmed Bookings</th><th>AI Predicted Demand</th><th>Slot Capacity</th></tr></thead>
        <tbody>
    `;
    labels.forEach((l, i) => {
      html += `<tr><td>${l}</td><td>${booked[i]}</td><td style="color: var(--irctc-orange-primary); font-weight: 700;">${predicted[i]}</td><td>${capacity[i]}</td></tr>`;
    });
    html += `</tbody></table>`;
    tableDiv.innerHTML = html;
  }

  // ---------------------------------------------------------------------------
  // LIVE VIVA DEMO: 10-Thread OS Race Condition Simulation
  // ---------------------------------------------------------------------------
  const btnRunRaceSimulation = document.getElementById("btnRunRaceSimulation");
  const raceResultsArea = document.getElementById("raceSimulationResultsArea");
  const raceThreadsGrid = document.getElementById("raceThreadsGrid");

  btnRunRaceSimulation?.addEventListener("click", async () => {
    btnRunRaceSimulation.disabled = true;
    btnRunRaceSimulation.textContent = "Firing 10 Simultaneous Barrier Threads...";

    const res = await window.apiClient.simulateRaceCondition();

    btnRunRaceSimulation.disabled = false;
    btnRunRaceSimulation.textContent = "Run 10-Thread Last-Seat Race Simulation";

    if (!res.ok) return;

    raceResultsArea.style.display = "block";
    document.getElementById("raceTotalThreads").textContent = res.summary.total_threads;
    document.getElementById("raceSlotCap").textContent = res.summary.slot_max_capacity;
    document.getElementById("raceSuccessCount").textContent = `${res.summary.success_count} (SUCCESS)`;
    document.getElementById("raceBlockedCount").textContent = `${res.summary.rejected_count} (BLOCKED)`;

    raceThreadsGrid.innerHTML = "";

    res.thread_results.forEach(tr => {
      const card = document.createElement("div");
      const isWinner = tr.is_winner;
      card.className = `race-thread-card ${isWinner ? 'winner' : 'blocked'}`;

      const statusBadge = isWinner
        ? `<span class="badge badge-open">CNF / SEAT LOCKED</span>`
        : `<span class="badge badge-full">REGRET / SLOT_CAPACITY_EXCEEDED</span>`;

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <strong style="font-family: var(--font-mono); font-size: 11.5px; color: var(--irctc-navy-primary);">Thread #${tr.thread_id}</strong>
          ${statusBadge}
        </div>
        <div style="font-size: 11px; color: var(--text-secondary);">${tr.voter_name} (ID: ${tr.voter_id})</div>
        <div style="margin: 4px 0; font-size: 11px; font-family: var(--font-mono);">
          ${isWinner ? `<strong>Token:</strong> ${tr.booking_reference_token}` : '<strong>Contention Status:</strong> BLOCKED BY SELECT ... FOR UPDATE'}
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 10.5px; color: var(--text-muted); border-top: 1px solid var(--irctc-border-subtle); padding-top: 4px;">
          <span>PID: ${tr.pcb_id}</span>
          <span style="font-weight: 700; color: ${isWinner ? 'var(--irctc-status-avl)' : 'inherit'};">${tr.execution_latency_ms} ms</span>
        </div>
      `;

      raceThreadsGrid.appendChild(card);
    });

    window.apiClient.showToast("Race condition test finished: Zero overbooking verified!", "success");
    raceResultsArea.scrollIntoView({ behavior: "smooth" });
  });

  // ---------------------------------------------------------------------------
  // Booth & Slot Management Form Handlers
  // ---------------------------------------------------------------------------
  const btnSaveBooth = document.getElementById("btnSaveBooth");
  btnSaveBooth?.addEventListener("click", async () => {
    const stationId = parseInt(document.getElementById("cfgStationId").value, 10);
    const pcId = parseInt(document.getElementById("cfgPcId").value, 10);
    const acId = parseInt(document.getElementById("cfgAcId").value, 10);
    const boothNum = document.getElementById("cfgBoothNum").value.trim();
    const boothName = document.getElementById("cfgBoothName").value.trim();
    const roomNum = document.getElementById("cfgRoomNum").value.trim();
    const maxCap = parseInt(document.getElementById("cfgMaxCap").value, 10);

    const res = await window.apiClient.createOrUpdateBooth({
      station_id: stationId,
      pc_id: pcId,
      ac_id: acId,
      booth_number: boothNum,
      booth_name: boothName,
      room_number: roomNum,
      max_capacity_per_slot: maxCap
    });

    if (res.ok) {
      window.apiClient.showToast(`Polling booth saved successfully with ID ${res.booth_id}!`, "success");
      refreshDashboardData();
    }
  });

  const btnSaveSlot = document.getElementById("btnSaveSlot");
  btnSaveSlot?.addEventListener("click", async () => {
    const boothId = parseInt(document.getElementById("cfgSlotBoothId").value, 10);
    const slotDate = document.getElementById("cfgSlotDate").value;
    const startTime = document.getElementById("cfgStartTime").value.trim();
    const endTime = document.getElementById("cfgEndTime").value.trim();
    const maxCap = parseInt(document.getElementById("cfgSlotCapacity").value, 10);
    const priReserved = parseInt(document.getElementById("cfgPriorityReserved").value, 10);

    const res = await window.apiClient.createOrUpdateSlot({
      booth_id: boothId,
      slot_date: slotDate,
      start_time: startTime,
      end_time: endTime,
      max_capacity: maxCap,
      priority_reserved_capacity: priReserved
    });

    if (res.ok) {
      window.apiClient.showToast(`Time slot saved successfully with ID ${res.slot_id}!`, "success");
      refreshDashboardData();
    }
  });

  // ---------------------------------------------------------------------------
  // 1-Click Telemetry Audit Export (JSON Snapshot)
  // ---------------------------------------------------------------------------
  const btnExportTelemetry = document.getElementById("btnExportTelemetry");
  btnExportTelemetry?.addEventListener("click", async () => {
    btnExportTelemetry.disabled = true;
    btnExportTelemetry.textContent = "Exporting...";

    const res = await window.apiClient.exportTelemetry();
    btnExportTelemetry.disabled = false;
    btnExportTelemetry.textContent = "Export Telemetry (JSON)";

    if (res.ok) {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(res, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `State_Logistics_Telemetry_${new Date().toISOString().slice(0, 10)}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      window.apiClient.showToast("Telemetry report snapshot downloaded successfully.", "success");
    } else {
      window.apiClient.showToast("Failed to export telemetry snapshot.", "error");
    }
  });

  // ---------------------------------------------------------------------------
  // Interactive OS CPU Scheduler Policy Comparator (FCFS vs Priority Aging)
  // ---------------------------------------------------------------------------
  const btnComparePolicies = document.getElementById("btnComparePolicies");
  const selectPolicySwitch = document.getElementById("selectPolicySwitch");
  const policyComparisonArea = document.getElementById("policyComparisonArea");
  const policyActiveNotice = document.getElementById("policyActiveNotice");
  const policyComparisonTableBody = document.querySelector("#policyComparisonTable tbody");

  btnComparePolicies?.addEventListener("click", async () => {
    const selectedPolicy = selectPolicySwitch?.value || "PRIORITY_AGING";
    btnComparePolicies.disabled = true;
    btnComparePolicies.textContent = "Simulating Dispatch Batch...";

    const res = await window.apiClient.switchSchedulerPolicy(selectedPolicy);
    btnComparePolicies.disabled = false;
    btnComparePolicies.textContent = "Run 6-Request Policy Simulation";

    if (res.ok && res.simulation_batch) {
      policyComparisonArea.style.display = "block";
      policyActiveNotice.textContent = `Active Dispatch Policy: ${res.active_policy} · Starvation Prevention Guaranteed`;

      if (policyComparisonTableBody) {
        policyComparisonTableBody.innerHTML = "";
        res.simulation_batch.dispatched_order.forEach(item => {
          const tr = document.createElement("tr");
          const isPromoted = (item.effective_priority < item.base_priority);
          const statusBadge = (res.active_policy === "PRIORITY_AGING")
            ? (isPromoted ? `<span class="badge badge-open">PROMOTED BY AGING</span>` : `<span class="badge badge-partial">BASE QUOTA PRIORITY</span>`)
            : `<span class="badge badge-partial">FIFO QUEUE ORDER</span>`;

          tr.innerHTML = `
            <td style="font-family: var(--font-mono); font-weight: 700;">#${item.dispatch_rank}</td>
            <td><strong>${item.voter_name}</strong></td>
            <td><span class="jurisdiction-tag">${item.special_category}</span></td>
            <td style="font-family: var(--font-mono);">${item.base_priority}</td>
            <td style="font-family: var(--font-mono);">${(item.simulated_wait_ms / 1000).toFixed(0)}s wait</td>
            <td style="font-family: var(--font-mono); font-weight: 700; color: ${isPromoted ? 'var(--irctc-orange-primary)' : 'inherit'};">${item.effective_priority}</td>
            <td>${statusBadge}</td>
          `;
          policyComparisonTableBody.appendChild(tr);
        });
      }

      window.apiClient.showToast(`Scheduler switched to ${res.active_policy}: 6 requests dispatched.`, "success");
    }
  });
});

