/**
 * Voter Portal Controller
 * Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
 * Module: frontend/js/voter_portal.js
 * 
 * Orchestrates:
 *   1. Step Navigation & Form state
 *   2. Synthetic voter lookup & registration
 *   3. Simulated ECI verification with explicit consent
 *   4. Haversine geo-ranking & interactive Leaflet map
 *   5. AI crowd demand forecasting & smart slot recommendation
 *   6. Concurrency-safe atomic booking, OS PCB animation, and pass slip management
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    currentStep: 1,
    voter: null,
    isVerified: false,
    simulatedToken: null,
    gps: { lat: 30.34215, lon: 78.02148 },
    accessibilityNeeded: false,
    selectedBooth: null,
    selectedSlot: null,
    activeAllocation: null,
    map: null,
    markers: []
  };

  // DOM Elements
  const stepIndicators = [
    document.getElementById("stepIndicator1"),
    document.getElementById("stepIndicator2"),
    document.getElementById("stepIndicator3"),
    document.getElementById("stepIndicator4")
  ];

  const stepSections = [
    document.getElementById("stepSection1"),
    document.getElementById("stepSection2"),
    document.getElementById("stepSection3"),
    document.getElementById("stepSection4")
  ];

  // Contrast Mode Toggle
  const contrastBtn = document.getElementById("contrastToggleBtn");
  if (contrastBtn) {
    contrastBtn.addEventListener("click", () => {
      document.body.classList.toggle("high-contrast-mode");
      const active = document.body.classList.contains("high-contrast-mode");
      contrastBtn.textContent = active ? "☀️ Normal Mode" : "👁️ High Contrast Mode";
    });
  }

  // ---------------------------------------------------------------------------
  // Step Navigation Helper
  // ---------------------------------------------------------------------------
  function goToStep(stepNumber) {
    if (stepNumber < 1 || stepNumber > 4) return;
    state.currentStep = stepNumber;

    stepSections.forEach((sec, idx) => {
      sec.style.display = (idx + 1 === stepNumber) ? "block" : "none";
    });

    stepIndicators.forEach((ind, idx) => {
      const stepIdx = idx + 1;
      ind.classList.remove("active", "completed");
      if (stepIdx === stepNumber) {
        ind.classList.add("active");
      } else if (stepIdx < stepNumber) {
        ind.classList.add("completed");
      }
    });

    // Special step initializers
    if (stepNumber === 3) {
      loadNearbyBooths();
    } else if (stepNumber === 4 && state.selectedBooth) {
      loadAvailableSlots(state.selectedBooth.booth_id);
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------------------------------------------------------------------------
  // STEP 1: Identification & Registration
  // ---------------------------------------------------------------------------
  const tabQuickSelect = document.getElementById("tabQuickSelect");
  const tabNewRegister = document.getElementById("tabNewRegister");
  const quickSelectPanel = document.getElementById("quickSelectPanel");
  const newRegisterPanel = document.getElementById("newRegisterPanel");
  const seededVoterSelect = document.getElementById("seededVoterSelect");
  const manualEpicInput = document.getElementById("manualEpicInput");
  const btnLookupEpic = document.getElementById("btnLookupEpic");
  const btnSubmitRegistration = document.getElementById("btnSubmitRegistration");
  const voterProfileCard = document.getElementById("voterProfileCard");
  const btnProceedToStep2 = document.getElementById("btnProceedToStep2");

  // Tab toggling
  tabQuickSelect.addEventListener("click", () => {
    quickSelectPanel.style.display = "block";
    newRegisterPanel.style.display = "none";
    tabQuickSelect.classList.add("active");
    tabNewRegister.classList.remove("active");
  });

  tabNewRegister.addEventListener("click", () => {
    quickSelectPanel.style.display = "none";
    newRegisterPanel.style.display = "block";
    tabNewRegister.classList.add("active");
    tabQuickSelect.classList.remove("active");
  });

  async function displayVoter(voter) {
    state.voter = voter;
    state.isVerified = (voter.simulated_verification_status === "SIMULATED_VERIFIED");

    document.getElementById("profVoterName").textContent = voter.full_name;
    document.getElementById("profVoterEpic").textContent = voter.demo_epic_no;
    document.getElementById("profCategoryBadge").textContent = `${voter.special_category} · PRIORITY ${voter.priority_level}`;
    document.getElementById("profBoothName").textContent = voter.booth_name || `Booth ${voter.assigned_booth_id}`;
    document.getElementById("profConstituency").textContent = `${voter.parliamentary_constituency || 'Tehri Garhwal (PC)'} · ${voter.assembly_constituency || 'Dehradun Cantt (AC)'}`;
    
    const verifElem = document.getElementById("profVerifStatus");
    if (state.isVerified) {
      verifElem.innerHTML = `<span style="color: var(--accent-emerald); font-weight: 700;">✅ SIMULATED_VERIFIED</span>`;
      document.getElementById("btnProceedToStep3").disabled = false;
    } else {
      verifElem.innerHTML = `<span style="color: var(--accent-amber); font-weight: 700;">⏳ UNVERIFIED</span>`;
    }

    voterProfileCard.style.display = "block";

    // Preselect accessibility if PwD or Senior
    if (voter.special_category === "PERSON_WITH_DISABILITY" || voter.special_category === "SENIOR_CITIZEN") {
      state.accessibilityNeeded = true;
      const chk = document.getElementById("accessibilityFilterCheck");
      if (chk) chk.checked = true;
    }
  }

  // Quick Select change
  seededVoterSelect.addEventListener("change", async (e) => {
    const epic = e.target.value;
    if (!epic) return;
    const res = await window.apiClient.lookupVoter(epic);
    if (res.ok && res.voter) {
      displayVoter(res.voter);
      window.apiClient.showToast(`Loaded voter profile for ${res.voter.full_name}`, "success");
    }
  });

  // Manual EPIC lookup
  btnLookupEpic.addEventListener("click", async () => {
    const epic = manualEpicInput.value.trim().toUpperCase();
    if (!epic) {
      window.apiClient.showToast("Please enter a synthetic EPIC number.", "warning");
      return;
    }
    const res = await window.apiClient.lookupVoter(epic);
    if (res.ok && res.voter) {
      displayVoter(res.voter);
      window.apiClient.showToast(`Found: ${res.voter.full_name}`, "success");
    }
  });

  // Submit new registration
  btnSubmitRegistration.addEventListener("click", async () => {
    const epic = document.getElementById("regEpicNo").value.trim().toUpperCase();
    const fullName = document.getElementById("regFullName").value.trim();
    const dob = document.getElementById("regDob").value;
    const gender = document.getElementById("regGender").value;
    const category = document.getElementById("regCategory").value;
    const boothId = parseInt(document.getElementById("regBoothSelect").value, 10);

    if (!fullName) {
      window.apiClient.showToast("Full name is required.", "warning");
      return;
    }

    const res = await window.apiClient.registerVoter({
      demo_epic_no: epic,
      full_name: fullName,
      dob: dob,
      gender: gender,
      special_category: category,
      assigned_booth_id: boothId
    });

    if (res.ok && res.voter) {
      window.apiClient.showToast(`Voter registered successfully!`, "success");
      displayVoter(res.voter);
    }
  });

  btnProceedToStep2.addEventListener("click", () => {
    if (!state.voter) {
      window.apiClient.showToast("Please select or register a voter first.", "warning");
      return;
    }
    goToStep(2);
  });

  // ---------------------------------------------------------------------------
  // STEP 2: Simulated ECI Verification
  // ---------------------------------------------------------------------------
  const consentCheckbox = document.getElementById("consentCheckbox");
  const verifMethodSelect = document.getElementById("verifMethodSelect");
  const simulatedInput = document.getElementById("simulatedInput");
  const btnExecuteVerification = document.getElementById("btnExecuteVerification");
  const verifResultToken = document.getElementById("verifResultToken");
  const verifBadgeState = document.getElementById("verifBadgeState");
  const btnProceedToStep3 = document.getElementById("btnProceedToStep3");
  const btnBackToStep1 = document.getElementById("btnBackToStep1");

  btnBackToStep1.addEventListener("click", () => goToStep(1));

  btnExecuteVerification.addEventListener("click", async () => {
    if (!consentCheckbox.checked) {
      window.apiClient.showToast("Explicit consent is mandatory for simulated ECI verification.", "warning");
      return;
    }

    const method = verifMethodSelect.value;
    const mockInput = simulatedInput.value.trim() || null;

    btnExecuteVerification.disabled = true;
    btnExecuteVerification.textContent = "Verifying...";

    const res = await window.apiClient.verifyMock(
      state.voter.voter_id,
      state.voter.assigned_booth_id,
      true,
      method,
      mockInput
    );

    btnExecuteVerification.disabled = false;
    btnExecuteVerification.textContent = "⚡ Execute Simulated Verification";

    if (res.ok && res.simulated_token) {
      state.isVerified = true;
      state.simulatedToken = res.simulated_token;
      verifBadgeState.textContent = "VERIFIED (SIMULATED)";
      verifBadgeState.className = "badge badge-open";
      verifResultToken.textContent = `Token: ${res.simulated_token} (${method})`;
      btnProceedToStep3.disabled = false;
      window.apiClient.showToast("Simulated identity verified successfully!", "success");
    }
  });

  btnProceedToStep3.addEventListener("click", () => {
    if (!state.isVerified) {
      window.apiClient.showToast("Please complete simulated verification first.", "warning");
      return;
    }
    goToStep(3);
  });

  // ---------------------------------------------------------------------------
  // STEP 3: Nearby Booths & Geospatial Map
  // ---------------------------------------------------------------------------
  const boothListContainer = document.getElementById("boothListContainer");
  const accessibilityFilterCheck = document.getElementById("accessibilityFilterCheck");
  const btnProceedToStep4 = document.getElementById("btnProceedToStep4");
  const btnBackToStep2 = document.getElementById("btnBackToStep2");

  btnBackToStep2.addEventListener("click", () => goToStep(2));

  // Presets
  document.getElementById("presetDdnCantt").addEventListener("click", () => {
    state.gps = { lat: 30.34215, lon: 78.02148 };
    loadNearbyBooths();
  });
  document.getElementById("presetRajpurRd").addEventListener("click", () => {
    state.gps = { lat: 30.33982, lon: 78.04871 };
    loadNearbyBooths();
  });
  document.getElementById("presetRishikesh").addEventListener("click", () => {
    state.gps = { lat: 30.10342, lon: 78.29471 };
    loadNearbyBooths();
  });
  document.getElementById("presetHaridwar").addEventListener("click", () => {
    state.gps = { lat: 29.93254, lon: 78.11892 };
    loadNearbyBooths();
  });

  accessibilityFilterCheck.addEventListener("change", (e) => {
    state.accessibilityNeeded = e.target.checked;
    loadNearbyBooths();
  });

  async function loadNearbyBooths() {
    boothListContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Calculating Haversine distances...</div>`;

    const res = await window.apiClient.getNearbyBooths(
      state.gps.lat,
      state.gps.lon,
      null,
      state.accessibilityNeeded
    );

    if (!res.ok || !res.booths) {
      boothListContainer.innerHTML = `<div style="color: var(--accent-crimson); padding: 1rem;">Failed to load nearby booths.</div>`;
      return;
    }

    renderBoothList(res.booths);
    initOrUpdateMap(res.booths);
  }

  function renderBoothList(booths) {
    boothListContainer.innerHTML = "";
    if (booths.length === 0) {
      boothListContainer.innerHTML = `<div style="color: var(--text-muted); padding: 1.5rem;">No booths matching your criteria.</div>`;
      return;
    }

    booths.forEach((b) => {
      const card = document.createElement("div");
      card.className = `booth-card ${state.selectedBooth?.booth_id === b.booth_id ? 'selected' : ''}`;
      
      const isAssigned = (state.voter && state.voter.assigned_booth_id === b.booth_id);

      card.innerHTML = `
        <div class="booth-card-header">
          <div>
            <div class="booth-card-title">${b.station_name}</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary);">${b.booth_name} (${b.room_number})</div>
          </div>
          <div class="booth-distance-tag">${b.distance_km} km</div>
        </div>
        <div class="booth-jurisdiction-tags">
          <span class="jurisdiction-tag">🏛️ PC: ${b.parliamentary_constituency}</span>
          <span class="jurisdiction-tag">🗳️ AC: ${b.assembly_constituency}</span>
          ${b.has_wheelchair_ramp ? '<span class="jurisdiction-tag" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">♿ Wheelchair Ramp</span>' : ''}
          ${isAssigned ? '<span class="badge badge-open" style="font-size: 0.65rem;">YOUR ASSIGNED BOOTH</span>' : ''}
        </div>
        <div style="font-size: 0.78rem; color: var(--text-muted);">
          📍 ${b.station_address} · Capacity: ${b.max_capacity_per_slot} per slot
        </div>
      `;

      card.addEventListener("click", () => {
        document.querySelectorAll(".booth-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        state.selectedBooth = b;
        btnProceedToStep4.disabled = false;
        btnProceedToStep4.textContent = `Select ${b.booth_name} & Proceed ➔`;
      });

      // Default select voter's assigned booth or the closest booth
      if (!state.selectedBooth && (isAssigned || booths.indexOf(b) === 0)) {
        state.selectedBooth = b;
        card.classList.add("selected");
        btnProceedToStep4.disabled = false;
        btnProceedToStep4.textContent = `Select ${b.booth_name} & Proceed ➔`;
      }

      boothListContainer.appendChild(card);
    });
  }

  function initOrUpdateMap(booths) {
    if (typeof L === "undefined" || window.leafletFailed) {
      document.getElementById("mapOfflineFallback").style.display = "flex";
      return;
    }

    if (!state.map) {
      try {
        state.map = L.map("boothMap").setView([state.gps.lat, state.gps.lon], 13);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; OpenStreetMap contributors'
        }).addTo(state.map);
      } catch (e) {
        document.getElementById("mapOfflineFallback").style.display = "flex";
        return;
      }
    } else {
      state.map.setView([state.gps.lat, state.gps.lon], 13);
      state.markers.forEach(m => state.map.removeLayer(m));
      state.markers = [];
    }

    // Voter location pin
    const voterMarker = L.circleMarker([state.gps.lat, state.gps.lon], {
      radius: 9,
      fillColor: "#06b6d4",
      color: "#ffffff",
      weight: 3,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(state.map).bindPopup("<b>Your Current Location</b>").openPopup();
    state.markers.push(voterMarker);

    // Station pins
    booths.forEach(b => {
      const lat = parseFloat(b.latitude) || (state.gps.lat + (Math.random() - 0.5) * 0.02);
      const lon = parseFloat(b.longitude) || (state.gps.lon + (Math.random() - 0.5) * 0.02);

      const marker = L.marker([lat, lon]).addTo(state.map);
      marker.bindPopup(`
        <b>${b.station_name}</b><br/>
        ${b.booth_name}<br/>
        Distance: ${b.distance_km} km<br/>
        ${b.has_wheelchair_ramp ? '♿ Accessible Ramp' : ''}
      `);
      state.markers.push(marker);
    });
  }

  btnProceedToStep4.addEventListener("click", () => {
    if (!state.selectedBooth) {
      window.apiClient.showToast("Please choose a polling booth.", "warning");
      return;
    }
    goToStep(4);
  });

  // ---------------------------------------------------------------------------
  // STEP 4: Slots & AI Demand Recommendation
  // ---------------------------------------------------------------------------
  const slotsGridContainer = document.getElementById("slotsGridContainer");
  const selectedBoothSummary = document.getElementById("selectedBoothSummary");
  const aiRecommendationBanner = document.getElementById("aiRecommendationBanner");
  const aiRecommendationText = document.getElementById("aiRecommendationText");
  const btnBookSlot = document.getElementById("btnBookSlot");
  const btnBackToStep3 = document.getElementById("btnBackToStep3");
  const pcbPipelineContainer = document.getElementById("pcbPipelineContainer");
  const appointmentSlipContainer = document.getElementById("appointmentSlipContainer");
  const btnCancelAllocation = document.getElementById("btnCancelAllocation");

  btnBackToStep3.addEventListener("click", () => goToStep(3));

  async function loadAvailableSlots(boothId) {
    selectedBoothSummary.textContent = `Showing time-slots for ${state.selectedBooth.station_name} (${state.selectedBooth.booth_name})`;
    slotsGridContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Predicting crowd arrival curve with AI...</div>`;

    const res = await window.apiClient.getAvailableSlots(
      boothId,
      state.voter ? state.voter.voter_id : null
    );

    if (!res.ok || !res.slots) {
      slotsGridContainer.innerHTML = `<div style="color: var(--accent-crimson); padding: 1.5rem;">Failed to load time slots.</div>`;
      return;
    }

    if (res.recommendation && res.recommendation.recommendation_reason) {
      aiRecommendationBanner.style.display = "flex";
      aiRecommendationText.textContent = res.recommendation.recommendation_reason;
    }

    renderSlotsGrid(res.slots);
  }

  function renderSlotsGrid(slots) {
    slotsGridContainer.innerHTML = "";

    slots.forEach(s => {
      const card = document.createElement("div");
      const isRecommended = s.is_recommended;
      card.className = `slot-card ${isRecommended ? 'recommended' : ''}`;
      
      const avail = s.available_capacity;
      const total = s.max_capacity;
      const pct = Math.min(100, Math.round(((total - avail) / total) * 100));

      let badgeClass = "badge-open";
      if (s.occupancy_status === "FULL") badgeClass = "badge-full";
      else if (s.occupancy_status === "PARTIALLY_OCCUPIED") badgeClass = "badge-partial";

      let fillBg = "#10b981";
      if (pct > 70) fillBg = "#f59e0b";
      if (pct >= 95) fillBg = "#ef4444";

      const ai = s.ai_crowd_forecast || {};

      card.innerHTML = `
        ${isRecommended ? '<div class="recommended-ribbon">⭐ AI Best Pick</div>' : ''}
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="badge ${badgeClass}">${s.occupancy_status}</span>
          <span style="font-size: 0.72rem; color: var(--text-muted);">${s.slot_date}</span>
        </div>
        <div class="slot-time-range">${s.start_time} - ${s.end_time}</div>
        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-secondary);">
          <span>Seats Available: <strong>${avail} / ${total}</strong></span>
          <span>${pct}% booked</span>
        </div>
        <div class="slot-capacity-bar">
          <div class="slot-capacity-fill" style="width: ${pct}%; background: ${fillBg};"></div>
        </div>
        <div style="background: rgba(0, 0, 0, 0.25); border-radius: var(--radius-sm); padding: 0.6rem; font-size: 0.75rem; margin-top: 0.5rem;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
            <span>🤖 Predicted Crowd:</span>
            <strong style="color: var(--accent-cyan);">${ai.predicted_arrivals || '~30'} voters</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
            <span>🚦 Congestion Level:</span>
            <strong class="badge badge-${(ai.congestion_level || 'LOW').toLowerCase().slice(0, 4)}">${ai.congestion_level || 'LOW'}</strong>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span>⏱️ Estimated Wait:</span>
            <strong>~${ai.estimated_wait_minutes || '8'} mins</strong>
          </div>
        </div>
      `;

      if (s.occupancy_status !== "FULL") {
        card.addEventListener("click", () => {
          document.querySelectorAll(".slot-card").forEach(c => c.classList.remove("selected"));
          card.classList.add("selected");
          state.selectedSlot = s;
          btnBookSlot.disabled = false;
          btnBookSlot.textContent = `🎟️ Book Slot ${s.start_time} - ${s.end_time} (OS Mutex Locked)`;
        });

        // Auto select recommended slot
        if (isRecommended && !state.selectedSlot) {
          card.classList.add("selected");
          state.selectedSlot = s;
          btnBookSlot.disabled = false;
          btnBookSlot.textContent = `🎟️ Book Slot ${s.start_time} - ${s.end_time} (OS Mutex Locked)`;
        }
      } else {
        card.style.opacity = "0.5";
        card.style.cursor = "not-allowed";
      }

      slotsGridContainer.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // Booking Execution & OS PCB Pipeline Animation
  // ---------------------------------------------------------------------------
  btnBookSlot.addEventListener("click", async () => {
    if (!state.voter || !state.selectedBooth || !state.selectedSlot) {
      window.apiClient.showToast("Missing required booking parameters.", "warning");
      return;
    }

    btnBookSlot.disabled = true;
    btnBookSlot.textContent = "Acquiring OS Mutex...";

    // Show and reset PCB pipeline
    pcbPipelineContainer.style.display = "block";
    resetPcbNodes();

    // Step 1: NEW
    activatePcbNode("pcbNodeNew");
    await sleep(200);

    // Step 2: READY (Enqueued)
    activatePcbNode("pcbNodeReady");
    await sleep(200);

    // Step 3: RUNNING (Dispatched)
    activatePcbNode("pcbNodeRunning");
    await sleep(150);

    // Step 4: WAITING (Entering mutex critical section)
    activatePcbNode("pcbNodeWaiting");

    const t0 = performance.now();
    const res = await window.apiClient.createAllocation(
      state.voter.voter_id,
      state.selectedBooth.booth_id,
      state.selectedSlot.slot_id,
      "USER_RESERVED"
    );
    const latency = (performance.now() - t0).toFixed(2);

    btnBookSlot.disabled = false;
    btnBookSlot.textContent = "🎟️ Confirm & Allocate Time Slot (OS Mutex Locked)";

    if (!res.ok) {
      resetPcbNodes();
      return;
    }

    // Step 5: TERMINATED
    activatePcbNode("pcbNodeTerminated");
    document.getElementById("pcbIdTag").textContent = `PID: ${res.pcb_telemetry?.process_id || 'PROC-ACID'}`;
    document.getElementById("pcbLatencyTag").textContent = `${latency} ms`;

    state.activeAllocation = res;
    window.apiClient.showToast("Time slot successfully allocated and committed to database!", "success");

    // Render Digital Appointment Slip
    renderAppointmentSlip(res);
  });

  function resetPcbNodes() {
    ["pcbNodeNew", "pcbNodeReady", "pcbNodeRunning", "pcbNodeWaiting", "pcbNodeTerminated"].forEach(id => {
      const node = document.getElementById(id);
      node.classList.remove("active", "completed");
    });
  }

  function activatePcbNode(nodeId) {
    const node = document.getElementById(nodeId);
    node.classList.add("active");
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function renderAppointmentSlip(alloc) {
    document.getElementById("slipVoterName").textContent = state.voter.full_name;
    document.getElementById("slipEpicNo").textContent = state.voter.demo_epic_no;
    document.getElementById("slipConstituency").textContent = `${state.selectedBooth.parliamentary_constituency} (PC) · ${state.selectedBooth.assembly_constituency} (AC)`;
    document.getElementById("slipStationBooth").textContent = `${state.selectedBooth.station_name} · ${state.selectedBooth.booth_name}`;
    document.getElementById("slipTimeWindow").textContent = `${state.selectedSlot.slot_date} | ${state.selectedSlot.start_time} - ${state.selectedSlot.end_time}`;
    document.getElementById("slipQueueNo").textContent = `#${String(alloc.queue_number || alloc.queue_token_no || 1).padStart(2, '0')}`;
    document.getElementById("slipTokenCode").textContent = alloc.booking_reference_token;

    const priBadge = document.getElementById("slipPriorityBadge");
    if (state.voter.priority_level === 1) {
      priBadge.textContent = "⭐ PRIORITY FAST-TRACK PASS";
      priBadge.className = "badge badge-open";
    } else {
      priBadge.textContent = "STANDARD SCHEDULED PASS";
      priBadge.className = "badge badge-partial";
    }

    appointmentSlipContainer.style.display = "block";
    appointmentSlipContainer.scrollIntoView({ behavior: "smooth" });
  }

  // Cancel allocation
  btnCancelAllocation.addEventListener("click", async () => {
    if (!state.activeAllocation || !state.activeAllocation.booking_reference_token) return;

    if (!confirm("Are you sure you want to cancel this booking and free the slot capacity?")) {
      return;
    }

    const token = state.activeAllocation.booking_reference_token;
    btnCancelAllocation.disabled = true;
    btnCancelAllocation.textContent = "Cancelling...";

    const res = await window.apiClient.cancelAllocation(token);
    btnCancelAllocation.disabled = false;
    btnCancelAllocation.textContent = "❌ Cancel / Free Slot Capacity";

    if (res.ok) {
      window.apiClient.showToast("Booking cancelled and slot capacity restored.", "success");
      appointmentSlipContainer.style.display = "none";
      state.activeAllocation = null;
      loadAvailableSlots(state.selectedBooth.booth_id);
    }
  });

  // Check health on start
  window.apiClient.checkHealth().then(h => {
    if (h.ok) console.log("Backend API Health verified:", h.service);
  });
});
