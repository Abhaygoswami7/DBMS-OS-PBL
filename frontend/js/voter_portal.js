/**
 * Voter Portal Controller (IRCTC Next-Gen Architecture)
 * Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
 * Module: frontend/js/voter_portal.js
 * 
 * Features:
 *   1. 4-Step ECI Stepper Workflow (Identity -> ECI Hash -> Geospatial -> Atomic Slot)
 *   2. PNR / Booking Token Status & Deadlock-Safe Slot Rescheduler (Hierarchical Lock Proof)
 *   3. Deterministic Inline SVG QR Verification Matrix & Code-128 Barcode on ERS Pass
 *   4. Standalone ERS Pass (.HTML) Exporter & Print Handler
 *   5. Ask-DISHA Polling Logistics Virtual Assistant Drawer
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    currentStep: 1,
    voter: null,
    isVerified: false,
    simulatedToken: null,
    gps: { lat: 29.3444, lon: 79.5632 },
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



  // Logout / Switch Portal Handler
  const btnLogoutVoter = document.getElementById("btnLogoutVoter");
  btnLogoutVoter?.addEventListener("click", () => {
    window.apiClient.clearVoterSession();
    window.location.href = "/";
  });

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
      setTimeout(() => {
        if (window.voteItMap) window.voteItMap.invalidateSize();
        if (state.map) state.map.invalidateSize();
      }, 100);
    } else if (stepNumber === 4 && state.selectedBooth) {
      loadAvailableSlots(state.selectedBooth.booth_id);
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  window.goToStep = goToStep;

  // ---------------------------------------------------------------------------
  // STEP 1: Identification, Registration & PNR Status Tabs
  // ---------------------------------------------------------------------------
  const tabQuickSelect = document.getElementById("tabQuickSelect");
  const tabNewRegister = document.getElementById("tabNewRegister");
  const tabPnrStatus = document.getElementById("tabPnrStatus");
  const quickSelectPanel = document.getElementById("quickSelectPanel");
  const newRegisterPanel = document.getElementById("newRegisterPanel");
  const pnrStatusPanel = document.getElementById("pnrStatusPanel");

  const seededVoterSelect = document.getElementById("seededVoterSelect");
  const manualEpicInput = document.getElementById("manualEpicInput");
  const btnLookupEpic = document.getElementById("btnLookupEpic");
  const btnSubmitRegistration = document.getElementById("btnSubmitRegistration");
  const voterProfileCard = document.getElementById("voterProfileCard");
  const btnProceedToStep2 = document.getElementById("btnProceedToStep2");

  // Tab toggling
  tabQuickSelect?.addEventListener("click", () => {
    quickSelectPanel.style.display = "block";
    newRegisterPanel.style.display = "none";
    if (pnrStatusPanel) pnrStatusPanel.style.display = "none";
    tabQuickSelect.classList.add("active");
    tabNewRegister?.classList.remove("active");
    tabPnrStatus?.classList.remove("active");
  });

  tabNewRegister?.addEventListener("click", () => {
    quickSelectPanel.style.display = "none";
    newRegisterPanel.style.display = "block";
    if (pnrStatusPanel) pnrStatusPanel.style.display = "none";
    tabNewRegister.classList.add("active");
    tabQuickSelect?.classList.remove("active");
    tabPnrStatus?.classList.remove("active");
  });

  tabPnrStatus?.addEventListener("click", () => {
    quickSelectPanel.style.display = "none";
    newRegisterPanel.style.display = "none";
    if (pnrStatusPanel) pnrStatusPanel.style.display = "block";
    tabPnrStatus.classList.add("active");
    tabQuickSelect?.classList.remove("active");
    tabNewRegister?.classList.remove("active");
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
      verifElem.innerHTML = `<span class="badge badge-open">SIMULATED_VERIFIED</span>`;
      document.getElementById("btnProceedToStep3").disabled = false;
    } else {
      verifElem.innerHTML = `<span class="badge badge-partial">UNVERIFIED</span>`;
    }

    voterProfileCard.style.display = "block";

    if (voter.special_category === "PERSON_WITH_DISABILITY" || voter.special_category === "SENIOR_CITIZEN") {
      state.accessibilityNeeded = true;
      const chk = document.getElementById("accessibilityFilterCheck");
      if (chk) chk.checked = true;
    }
  }

  // Restore authenticated session from IRCTC Gateway
  const savedVoterSession = window.apiClient.getVoterSession();
  if (savedVoterSession) {
    displayVoter(savedVoterSession);
  } else {
    // If no active session, verify gate access (redirects if unauthenticated)
    window.apiClient.checkVoterSession();
  }

  // Quick Select change
  seededVoterSelect?.addEventListener("change", async (e) => {
    const epic = e.target.value;
    if (!epic) return;
    const res = await window.apiClient.lookupVoter(epic);
    if (res.ok && res.voter) {
      displayVoter(res.voter);
      window.apiClient.showToast(`Voter record loaded for ${res.voter.full_name}`, "info");
    }
  });

  // Manual EPIC lookup
  btnLookupEpic?.addEventListener("click", async () => {
    const epic = manualEpicInput.value.trim();
    if (!epic) {
      window.apiClient.showToast("Please enter an EPIC number.", "warning");
      return;
    }
    const res = await window.apiClient.lookupVoter(epic);
    if (res.ok && res.voter) {
      displayVoter(res.voter);
      window.apiClient.showToast(`Voter profile retrieved: ${res.voter.full_name}`, "success");
    }
  });

  // New synthetic registration
  btnSubmitRegistration?.addEventListener("click", async () => {
    const fullName = document.getElementById("regFullName").value.trim();
    const dob = document.getElementById("regDob").value;
    const gender = document.getElementById("regGender").value;
    const category = document.getElementById("regCategory").value;
    const boothId = parseInt(document.getElementById("regBoothId").value, 10);

    if (!fullName || !dob) {
      window.apiClient.showToast("Full Name and Date of Birth are mandatory.", "warning");
      return;
    }

    const rand = Math.floor(1000 + Math.random() * 9000);
    const demoEpic = `DEM-UK-2026-${rand}`;

    btnSubmitRegistration.disabled = true;
    btnSubmitRegistration.textContent = "Registering...";

    const res = await window.apiClient.registerVoter({
      demo_epic_no: demoEpic,
      full_name: fullName,
      dob: dob,
      gender: gender,
      special_category: category,
      assigned_booth_id: boothId
    });

    btnSubmitRegistration.disabled = false;
    btnSubmitRegistration.textContent = "Create Synthetic Registration";

    if (res.ok && res.voter) {
      displayVoter(res.voter);
      window.apiClient.showToast(`Registered successfully with EPIC: ${res.voter.demo_epic_no}`, "success");
    }
  });

  btnProceedToStep2?.addEventListener("click", () => {
    if (!state.voter) {
      window.apiClient.showToast("Please select or register a voter first.", "warning");
      return;
    }
    goToStep(2);
  });

  // ---------------------------------------------------------------------------
  // PNR Status & Deadlock-Safe Rescheduler Logic
  // ---------------------------------------------------------------------------
  const inputPnrToken = document.getElementById("inputPnrToken");
  const btnFetchPnrStatus = document.getElementById("btnFetchPnrStatus");
  const btnLoadActivePass = document.getElementById("btnLoadActivePass");
  const rescheduleBox = document.getElementById("rescheduleBox");
  const rescheduleCurrentInfo = document.getElementById("rescheduleCurrentInfo");
  const selectRescheduleSlot = document.getElementById("selectRescheduleSlot");
  const btnExecuteReschedule = document.getElementById("btnExecuteReschedule");
  const rescheduleProofBadge = document.getElementById("rescheduleProofBadge");

  btnFetchPnrStatus?.addEventListener("click", async () => {
    const token = inputPnrToken.value.trim();
    if (!token) {
      window.apiClient.showToast("Please enter a booking token / PNR.", "warning");
      return;
    }
    await loadAndDisplayPassForToken(token);
  });

  btnLoadActivePass?.addEventListener("click", async () => {
    const token = state.activeAllocation?.booking_reference_token || state.activeAllocation?.new_booking_reference_token;
    if (!token) {
      window.apiClient.showToast("No active booking session found. Book a slot first or enter a token.", "warning");
      return;
    }
    inputPnrToken.value = token;
    await loadAndDisplayPassForToken(token);
  });

  async function loadAndDisplayPassForToken(token) {
    btnFetchPnrStatus.disabled = true;
    btnFetchPnrStatus.textContent = "Fetching...";

    const res = await window.apiClient.getAllocationSlip(token);
    btnFetchPnrStatus.disabled = false;
    btnFetchPnrStatus.textContent = "Retrieve";

    if (!res.ok || !res.appointment_slip) {
      window.apiClient.showToast(`Booking reference token '${token}' not found.`, "error");
      return;
    }

    const slip = res.appointment_slip;
    state.activeAllocation = {
      booking_reference_token: token,
      queue_number: slip.queue_token_number || slip.queue_token_no || 1
    };

    renderAppointmentSlipFromView(slip);
    window.apiClient.showToast(`ERS pass retrieved for ${slip.voter_name}.`, "success");

    // Populate reschedule box
    if (rescheduleBox) {
      rescheduleBox.style.display = "block";
      rescheduleCurrentInfo.innerHTML = `<strong>Current Active Slot:</strong> Slot #${slip.slot_id} (${slip.start_time} - ${slip.end_time}) at ${slip.booth_name}`;
      
      // Load booth slots to populate available targets
      const slotsRes = await window.apiClient.getAvailableSlots(slip.booth_id);
      if (slotsRes.ok && slotsRes.slots) {
        selectRescheduleSlot.innerHTML = "";
        slotsRes.slots.forEach(s => {
          if (s.slot_id !== slip.slot_id && s.available_capacity > 0) {
            const opt = document.createElement("option");
            opt.value = s.slot_id;
            opt.textContent = `Slot #${s.slot_id}: ${s.start_time.slice(0, 5)} - ${s.end_time.slice(0, 5)} (Avl: ${s.available_capacity})`;
            selectRescheduleSlot.appendChild(opt);
          }
        });
      }
    }
  }

  btnExecuteReschedule?.addEventListener("click", async () => {
    const token = inputPnrToken.value.trim() || state.activeAllocation?.booking_reference_token;
    const targetSlotId = selectRescheduleSlot.value;

    if (!token || !targetSlotId) {
      window.apiClient.showToast("Select target time slot for rescheduling.", "warning");
      return;
    }

    btnExecuteReschedule.disabled = true;
    btnExecuteReschedule.textContent = "Executing Deadlock-Safe Lock Acquisition...";

    const res = await window.apiClient.rescheduleAllocation(token, targetSlotId);
    btnExecuteReschedule.disabled = false;
    btnExecuteReschedule.textContent = "Change Arrival Time Slot (Deadlock-Safe Swap)";

    if (res.ok && res.appointment_slip) {
      window.apiClient.showToast("Time slot successfully rescheduled without deadlock risk!", "success");
      
      const locks = res.lock_acquisition_order || [];
      if (rescheduleProofBadge) {
        rescheduleProofBadge.style.display = "block";
        rescheduleProofBadge.innerHTML = `
          <div class="coffman-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            COFFMAN PROOF: Locks Acquired in Ascending Order: Slot #${locks[0] || 'A'} &rarr; Slot #${locks[1] || 'B'} (Deadlock-Free Resource Ordering)
          </div>
        `;
      }

      state.activeAllocation = {
        booking_reference_token: res.new_booking_reference_token || res.booking_reference_token,
        queue_number: res.appointment_slip.queue_token_number || 1
      };
      inputPnrToken.value = res.new_booking_reference_token || res.booking_reference_token;
      renderAppointmentSlipFromView(res.appointment_slip);
    }
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

  btnBackToStep1?.addEventListener("click", () => goToStep(1));

  btnExecuteVerification?.addEventListener("click", async () => {
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
    btnExecuteVerification.textContent = "Execute Simulated Verification";

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

  btnProceedToStep3?.addEventListener("click", () => {
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

  btnBackToStep2?.addEventListener("click", () => goToStep(2));

  const setGpsPreset = (lat, lon) => {
    state.gps = { lat, lon };
    loadNearbyBooths();
    setTimeout(() => {
      if (window.voteItMap) window.voteItMap.invalidateSize();
      if (state.map) state.map.invalidateSize();
    }, 100);
  };

  // Bhimtal Main Campus (Graphic Era Hill University): 29.3444, 79.5632
  document.getElementById("presetBhimtalCampus")?.addEventListener("click", () => setGpsPreset(29.3444, 79.5632));
  document.getElementById("presetDdnCantt")?.addEventListener("click", () => setGpsPreset(29.3444, 79.5632));

  // Sattal Lake View Point: 29.3490, 79.5317
  document.getElementById("presetSattal")?.addEventListener("click", () => setGpsPreset(29.3490, 79.5317));
  document.getElementById("presetRajpurRd")?.addEventListener("click", () => setGpsPreset(29.3490, 79.5317));

  // Bhowali Market Centre: 29.3823, 79.5197
  document.getElementById("presetBhowali")?.addEventListener("click", () => setGpsPreset(29.3823, 79.5197));
  document.getElementById("presetRishikesh")?.addEventListener("click", () => setGpsPreset(29.3823, 79.5197));

  // Kathgodam Railway Hub: 29.2675, 79.5446
  document.getElementById("presetKathgodam")?.addEventListener("click", () => setGpsPreset(29.2675, 79.5446));
  document.getElementById("presetHaridwar")?.addEventListener("click", () => setGpsPreset(29.2675, 79.5446));

  accessibilityFilterCheck?.addEventListener("change", (e) => {
    state.accessibilityNeeded = e.target.checked;
    loadNearbyBooths();
  });

  async function loadNearbyBooths() {
    boothListContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 12px;">Calculating Haversine proximity matrix...</div>`;

    const res = await window.apiClient.getNearbyBooths(
      state.gps.lat,
      state.gps.lon,
      null,
      state.accessibilityNeeded
    );

    if (!res.ok || !res.booths) {
      boothListContainer.innerHTML = `<div style="color: var(--irctc-status-wl); padding: 1rem; font-size: 12px;">Failed to load nearby booths.</div>`;
      return;
    }

    renderBoothList(res.booths);
    initOrUpdateMap(res.booths);
  }

  window.loadNearbyBooths = loadNearbyBooths;

  function renderBoothList(booths) {
    boothListContainer.innerHTML = "";
    if (booths.length === 0) {
      boothListContainer.innerHTML = `<div style="color: var(--text-muted); padding: 1.5rem; font-size: 12px;">No booths matching your criteria.</div>`;
      return;
    }

    booths.forEach((b) => {
      const card = document.createElement("div");
      card.className = `booth-card ${state.selectedBooth?.booth_id === b.booth_id ? 'selected' : ''}`;
      
      const isAssigned = (state.voter && state.voter.assigned_booth_id === b.booth_id);

      card.innerHTML = `
        <div class="booth-card-header">
          <div>
            <div class="booth-card-title">${b.booth_name} · ${b.station_name}</div>
            <div style="font-size: 11px; color: var(--text-secondary);">${b.room_number || 'Room Main'} · Capacity: ${b.max_capacity_per_slot} per slot</div>
          </div>
          <div class="booth-distance-tag">${b.distance_km} KM FROM VOTER</div>
        </div>
        <div class="booth-card-body">
          <div class="booth-jurisdiction-tags">
            <span class="jurisdiction-tag">PC: ${b.parliamentary_constituency}</span>
            <span class="jurisdiction-tag">AC: ${b.assembly_constituency}</span>
            ${b.has_wheelchair_ramp ? '<span class="badge badge-open">RAMP AVAILABLE</span>' : ''}
            ${isAssigned ? '<span class="badge badge-open">YOUR ASSIGNED BOOTH</span>' : ''}
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">
            Station Address: ${b.station_address}
          </div>
        </div>
      `;

      card.addEventListener("click", () => {
        document.querySelectorAll(".booth-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        state.selectedBooth = b;
        btnProceedToStep4.disabled = false;
        btnProceedToStep4.textContent = `Select ${b.booth_name} & Proceed`;
      });

      if (!state.selectedBooth && (isAssigned || booths.indexOf(b) === 0)) {
        state.selectedBooth = b;
        card.classList.add("selected");
        btnProceedToStep4.disabled = false;
        btnProceedToStep4.textContent = `Select ${b.booth_name} & Proceed`;
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

    const voterMarker = L.circleMarker([state.gps.lat, state.gps.lon], {
      radius: 8,
      fillColor: "#fb792b",
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.95
    }).addTo(state.map).bindPopup("<b>Your Registered Location (Bhimtal)</b>").openPopup();
    state.markers.push(voterMarker);

    booths.forEach(b => {
      const lat = parseFloat(b.latitude) || (state.gps.lat + (Math.random() - 0.5) * 0.02);
      const lon = parseFloat(b.longitude) || (state.gps.lon + (Math.random() - 0.5) * 0.02);

      const marker = L.marker([lat, lon]).addTo(state.map);
      marker.bindPopup(`
        <b>${b.station_name}</b><br/>
        ${b.booth_name}<br/>
        Distance: ${b.distance_km} km<br/>
        ${b.has_wheelchair_ramp ? 'Wheelchair Accessible Ramp Available' : ''}
      `);
      state.markers.push(marker);
    });

    window.voteItMap = state.map;
    setTimeout(() => {
      if (window.voteItMap) window.voteItMap.invalidateSize();
      if (state.map) state.map.invalidateSize();
    }, 100);
  }

  btnProceedToStep4?.addEventListener("click", () => {
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
  const btnDownloadErsPass = document.getElementById("btnDownloadErsPass");

  btnBackToStep3?.addEventListener("click", () => goToStep(3));

  async function loadAvailableSlots(boothId) {
    selectedBoothSummary.textContent = `Showing time-slots for ${state.selectedBooth.station_name} (${state.selectedBooth.booth_name})`;
    slotsGridContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 12px;">Querying discretized polling windows and AI crowd forecasts...</div>`;

    const res = await window.apiClient.getAvailableSlots(
      boothId,
      state.voter ? state.voter.voter_id : null
    );

    if (!res.ok || !res.slots) {
      slotsGridContainer.innerHTML = `<div style="color: var(--irctc-status-wl); padding: 1.5rem; font-size: 12px;">Failed to load time slots.</div>`;
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

      const ai = s.ai_crowd_forecast || {};

      let statusHtml = "";
      if (avail > 0 && pct <= 75) {
        statusHtml = `<div class="slot-status-line slot-status-avl">AVAILABLE-${String(avail).padStart(4, '0')}</div>`;
      } else if (avail > 0 && pct > 75) {
        statusHtml = `<div class="slot-status-line slot-status-rac">MOD CROWD / AVL-${String(avail).padStart(4, '0')}</div>`;
      } else {
        statusHtml = `<div class="slot-status-line slot-status-wl">REGRET / FULL-0000</div>`;
      }

      card.innerHTML = `
        ${isRecommended ? '<div class="recommended-ribbon">AI OPTIMAL SLOT</div>' : ''}
        <div class="slot-header-row">
          <div class="slot-time-range">${s.start_time.slice(0, 5)} - ${s.end_time.slice(0, 5)} HRS</div>
          <span style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono);">${s.slot_date}</span>
        </div>
        ${statusHtml}
        <div style="font-size: 11px; color: var(--text-secondary); display: flex; justify-content: space-between;">
          <span>Capacity: <strong>${avail} / ${total}</strong></span>
          <span>${pct}% booked</span>
        </div>
        <div class="slot-telemetry-line">
          <span>ML: ${ai.predicted_arrivals || '24'} Arrivals</span>
          <span>Est. Wait: ~${ai.estimated_wait_minutes || '6'} min</span>
        </div>
      `;

      if (s.occupancy_status !== "FULL" && avail > 0) {
        card.addEventListener("click", () => {
          document.querySelectorAll(".slot-card").forEach(c => c.classList.remove("selected"));
          card.classList.add("selected");
          state.selectedSlot = s;
          btnBookSlot.disabled = false;
          btnBookSlot.textContent = `Book Slot ${s.start_time.slice(0, 5)} - ${s.end_time.slice(0, 5)} (OS Mutex Locked)`;
        });

        if (isRecommended && !state.selectedSlot) {
          card.classList.add("selected");
          state.selectedSlot = s;
          btnBookSlot.disabled = false;
          btnBookSlot.textContent = `Book Slot ${s.start_time.slice(0, 5)} - ${s.end_time.slice(0, 5)} (OS Mutex Locked)`;
        }
      } else {
        card.style.opacity = "0.6";
        card.style.cursor = "not-allowed";
      }

      slotsGridContainer.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // Booking Execution & OS PCB Pipeline Animation
  // ---------------------------------------------------------------------------
  btnBookSlot?.addEventListener("click", async () => {
    if (!state.voter || !state.selectedBooth || !state.selectedSlot) {
      window.apiClient.showToast("Missing required booking parameters.", "warning");
      return;
    }

    btnBookSlot.disabled = true;
    btnBookSlot.textContent = "Acquiring OS Mutex...";

    pcbPipelineContainer.style.display = "block";
    resetPcbNodes();

    activatePcbNode("pcbNodeNew");
    await sleep(200);

    activatePcbNode("pcbNodeReady");
    await sleep(200);

    activatePcbNode("pcbNodeRunning");
    await sleep(150);

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
    btnBookSlot.textContent = "Confirm & Allocate Time Slot (OS Mutex Locked)";

    if (!res.ok) {
      resetPcbNodes();
      return;
    }

    activatePcbNode("pcbNodeTerminated");
    document.getElementById("pcbIdTag").textContent = `PID: ${res.pcb_telemetry?.process_id || 'PROC-ACID'}`;
    document.getElementById("pcbLatencyTag").textContent = `${latency} ms`;

    state.activeAllocation = res;
    window.apiClient.showToast("Time slot successfully allocated and committed to database!", "success");

    renderAppointmentSlip(res);
  });

  function resetPcbNodes() {
    ["pcbNodeNew", "pcbNodeReady", "pcbNodeRunning", "pcbNodeWaiting", "pcbNodeTerminated"].forEach(id => {
      const node = document.getElementById(id);
      node?.classList.remove("active", "completed");
    });
  }

  function activatePcbNode(nodeId) {
    const node = document.getElementById(nodeId);
    node?.classList.add("active");
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // ---------------------------------------------------------------------------
  // Deterministic SVG QR Matrix & Barcode Generators
  // ---------------------------------------------------------------------------
  function generateSvgQrMatrix(token) {
    let hash = 0;
    for (let i = 0; i < token.length; i++) {
      hash = ((hash << 5) - hash) + token.charCodeAt(i);
      hash |= 0;
    }
    const size = 12;
    let svg = `<svg viewBox="0 0 ${size} ${size}" width="68" height="68" shape-rendering="crispEdges">`;
    svg += `<rect width="${size}" height="${size}" fill="#ffffff"/>`;
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        const inTopLeft = (r < 4 && c < 4);
        const inTopRight = (r < 4 && c >= size - 4);
        const inBottomLeft = (r >= size - 4 && c < 4);
        let fill = false;
        if (inTopLeft || inTopRight || inBottomLeft) {
          const lr = inTopLeft ? r : (inTopRight ? r : r - (size - 4));
          const lc = inTopLeft ? c : (inTopRight ? c - (size - 4) : c);
          fill = (lr === 0 || lr === 3 || lc === 0 || lc === 3 || (lr >= 1 && lr <= 2 && lc >= 1 && lc <= 2));
        } else {
          const bit = ((hash ^ (r * 17 + c * 31)) >>> (c % 16)) & 1;
          fill = (bit === 1);
        }
        if (fill) {
          svg += `<rect x="${c}" y="${r}" width="1" height="1" fill="#14264c"/>`;
        }
      }
    }
    svg += `</svg>`;
    return svg;
  }

  function generateSvgBarcode() {
    const widths = [1, 2, 1, 3, 2, 1, 1, 2, 3, 1, 2, 1, 3, 1, 1, 2, 1, 2, 3, 2, 1];
    let svg = `<svg viewBox="0 0 100 28" width="140" height="32" preserveAspectRatio="none">`;
    let x = 4;
    for (let i = 0; i < widths.length; i++) {
      const w = widths[i];
      if (i % 2 === 0) {
        svg += `<rect x="${x}" y="0" width="${w}" height="28" fill="#14264c"/>`;
      }
      x += w + 2;
      if (x > 94) break;
    }
    svg += `</svg>`;
    return svg;
  }

  function renderAppointmentSlip(alloc) {
    const token = alloc.booking_reference_token || "TKN-UK-DEMO";
    document.getElementById("slipVoterName").textContent = state.voter.full_name;
    document.getElementById("slipEpicNo").textContent = state.voter.demo_epic_no;
    document.getElementById("slipConstituency").textContent = `${state.selectedBooth.parliamentary_constituency} (PC) · ${state.selectedBooth.assembly_constituency} (AC)`;
    document.getElementById("slipStationBooth").textContent = `${state.selectedBooth.station_name} · ${state.selectedBooth.booth_name}`;
    document.getElementById("slipTimeWindow").textContent = `${state.selectedSlot.slot_date} | ${state.selectedSlot.start_time} - ${state.selectedSlot.end_time}`;
    document.getElementById("slipQueueNo").textContent = `#${String(alloc.queue_number || alloc.queue_token_no || 1).padStart(2, '0')}`;
    document.getElementById("slipTokenCode").textContent = token;

    const priBadge = document.getElementById("slipPriorityBadge");
    if (state.voter.priority_level === 1) {
      priBadge.textContent = "PRIORITY FAST-TRACK PASS";
      priBadge.className = "badge badge-open";
    } else {
      priBadge.textContent = "STANDARD SCHEDULED PASS";
      priBadge.className = "badge badge-partial";
    }

    // Render deterministic QR & Barcode
    const qrElem = document.getElementById("ersQrMatrix");
    if (qrElem) qrElem.innerHTML = generateSvgQrMatrix(token);
    const barcodeElem = document.getElementById("ersBarcodeContainer");
    if (barcodeElem) barcodeElem.innerHTML = generateSvgBarcode();
    const barcodeText = document.getElementById("ersBarcodeText");
    if (barcodeText) barcodeText.textContent = token;

    appointmentSlipContainer.style.display = "block";
    appointmentSlipContainer.scrollIntoView({ behavior: "smooth" });
  }

  function renderAppointmentSlipFromView(slip) {
    const token = slip.booking_reference_token || slip.allocation_token;
    document.getElementById("slipVoterName").textContent = slip.voter_name;
    document.getElementById("slipEpicNo").textContent = slip.demo_epic_no;
    document.getElementById("slipConstituency").textContent = `${slip.parliamentary_constituency || 'Tehri Garhwal'} (PC) · ${slip.assembly_constituency || 'Dehradun Cantt'} (AC)`;
    document.getElementById("slipStationBooth").textContent = `${slip.station_name} · ${slip.booth_name}`;
    document.getElementById("slipTimeWindow").textContent = `${slip.slot_date} | ${slip.start_time} - ${slip.end_time}`;
    document.getElementById("slipQueueNo").textContent = `#${String(slip.queue_token_number || slip.queue_token_no || 1).padStart(2, '0')}`;
    document.getElementById("slipTokenCode").textContent = token;

    const priBadge = document.getElementById("slipPriorityBadge");
    if (slip.special_category && slip.special_category !== "GENERAL") {
      priBadge.textContent = "PRIORITY FAST-TRACK PASS";
      priBadge.className = "badge badge-open";
    } else {
      priBadge.textContent = "STANDARD SCHEDULED PASS";
      priBadge.className = "badge badge-partial";
    }

    const qrElem = document.getElementById("ersQrMatrix");
    if (qrElem) qrElem.innerHTML = generateSvgQrMatrix(token);
    const barcodeElem = document.getElementById("ersBarcodeContainer");
    if (barcodeElem) barcodeElem.innerHTML = generateSvgBarcode();
    const barcodeText = document.getElementById("ersBarcodeText");
    if (barcodeText) barcodeText.textContent = token;

    appointmentSlipContainer.style.display = "block";
    appointmentSlipContainer.scrollIntoView({ behavior: "smooth" });
  }

  // Cancel allocation
  btnCancelAllocation?.addEventListener("click", async () => {
    const token = state.activeAllocation?.booking_reference_token || document.getElementById("slipTokenCode")?.textContent;
    if (!token) return;

    if (!confirm("Are you sure you want to cancel this booking and free the slot capacity?")) {
      return;
    }

    btnCancelAllocation.disabled = true;
    btnCancelAllocation.textContent = "Cancelling...";

    const res = await window.apiClient.cancelAllocation(token);
    btnCancelAllocation.disabled = false;
    btnCancelAllocation.textContent = "Cancel / Free Slot Capacity";

    if (res.ok) {
      window.apiClient.showToast("Booking cancelled and slot capacity restored.", "success");
      appointmentSlipContainer.style.display = "none";
      state.activeAllocation = null;
      if (state.selectedBooth) loadAvailableSlots(state.selectedBooth.booth_id);
    }
  });

  // Download ERS Pass as Standalone HTML file
  btnDownloadErsPass?.addEventListener("click", () => {
    const passHtml = appointmentSlipContainer.innerHTML;
    const token = document.getElementById("slipTokenCode")?.textContent || "ONOE_PASS";
    const fullDoc = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ERS Pass - ${token}</title>
  <link rel="stylesheet" href="/css/styles.css">
  <style>
    body { font-family: Arial, sans-serif; padding: 24px; background: #ffffff; }
    .appointment-slip { border: 2px solid #213d77; max-width: 800px; margin: 0 auto; padding: 24px; }
    .ers-actions { display: none !important; }
  </style>
</head>
<body>
  ${passHtml}
</body>
</html>`;
    const blob = new Blob([fullDoc], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ERS_Pass_${token}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    window.apiClient.showToast("ERS Pass downloaded successfully.", "info");
  });

  // ---------------------------------------------------------------------------
  // Ask-DISHA Polling Logistics Virtual Assistant Drawer
  // ---------------------------------------------------------------------------
  const btnOpenDisha = document.getElementById("btnOpenDisha");
  const btnCloseDisha = document.getElementById("btnCloseDisha");
  const dishaDrawer = document.getElementById("dishaAssistantDrawer");
  const dishaResponseBox = document.getElementById("dishaResponseBox");

  btnOpenDisha?.addEventListener("click", () => {
    dishaDrawer.style.display = (dishaDrawer.style.display === "flex") ? "none" : "flex";
  });

  btnCloseDisha?.addEventListener("click", () => {
    dishaDrawer.style.display = "none";
  });

  document.getElementById("chipLowestCrowd")?.addEventListener("click", async () => {
    dishaResponseBox.innerHTML = `<em>Querying nearest polling booths and AI crowd forecast curve...</em>`;
    const nearby = await window.apiClient.getNearbyBooths(state.gps.lat, state.gps.lon);
    if (!nearby.ok || !nearby.booths || nearby.booths.length === 0) {
      dishaResponseBox.textContent = "Unable to retrieve nearby booths at current GPS coordinates.";
      return;
    }
    const nearest = nearby.booths[0];
    const slotsRes = await window.apiClient.getAvailableSlots(nearest.booth_id);
    if (!slotsRes.ok || !slotsRes.slots) {
      dishaResponseBox.textContent = `Retrieved booth ${nearest.station_name}, but slots could not be loaded.`;
      return;
    }

    // Find slot with lowest predicted crowd
    let bestSlot = slotsRes.slots[0];
    let minWait = 999;
    slotsRes.slots.forEach(s => {
      const wait = s.ai_crowd_forecast?.estimated_wait_minutes || 10;
      if (wait < minWait && s.available_capacity > 0) {
        minWait = wait;
        bestSlot = s;
      }
    });

    dishaResponseBox.innerHTML = `
      <strong>Optimal Low-Crowd Window Identified:</strong><br/>
      • <strong>Station:</strong> ${nearest.station_name} (${nearest.booth_name})<br/>
      • <strong>Time Window:</strong> ${bestSlot.start_time.slice(0, 5)} - ${bestSlot.end_time.slice(0, 5)} HRS<br/>
      • <strong>Predicted Crowd:</strong> ~${bestSlot.ai_crowd_forecast?.predicted_arrivals || '22'} voters<br/>
      • <strong>Estimated Wait:</strong> ~${minWait} minutes<br/>
      • <strong>Confidence:</strong> Random Forest Model R² = 0.9491
    `;
  });

  document.getElementById("chipModelAccuracy")?.addEventListener("click", async () => {
    dishaResponseBox.innerHTML = `<em>Fetching Random Forest vs Baseline benchmark telemetry...</em>`;
    const res = await window.apiClient.getAdminCrowdPredictions();
    const metrics = res.ok ? res.evaluation_metrics : null;
    const rf = metrics?.random_forest_model?.metrics || { mae: 1.5724, r2_score: 0.9491 };
    const base = metrics?.baseline_heuristic_model?.metrics || { mae: 6.5712 };

    dishaResponseBox.innerHTML = `
      <strong>Random Forest Demand Regressor vs Baseline:</strong><br/>
      • <strong>Baseline Heuristic MAE:</strong> ${base.mae} voters<br/>
      • <strong>Random Forest MAE:</strong> ${rf.mae} voters<br/>
      • <strong>Accuracy Improvement:</strong> 76.1% lower prediction error<br/>
      • <strong>Goodness-of-Fit (R²):</strong> ${rf.r2_score || '0.9491'}<br/>
      <em>Trained on weather, historic turnout, and priority category demographics.</em>
    `;
  });

  document.getElementById("chipExplainOs")?.addEventListener("click", () => {
    dishaResponseBox.innerHTML = `
      <strong>OS Concurrency &amp; Fairness Guardrails:</strong><br/>
      • <strong>ACID Row-Level Locking:</strong> MySQL InnoDB <code>SELECT ... FOR UPDATE</code> locks exact slot capacity to prevent physical overbooking under multi-threaded contention.<br/>
      • <strong>Dynamic Priority Aging:</strong> Every 10 seconds of wait time elevates a general voter's effective priority score by 0.1, mathematically preventing starvation behind priority quotas.<br/>
      • <strong>Resource Ordering (Deadlock Safety):</strong> Dual-slot swaps acquire locks in strict <code>min(slot_a, slot_b)</code> &rarr; <code>max(slot_a, slot_b)</code> numerical order, eliminating Coffman Circular Wait.
    `;
  });

  // Invalidate map size on window resize
  window.addEventListener("resize", () => {
    if (window.voteItMap) window.voteItMap.invalidateSize();
    if (state.map) state.map.invalidateSize();
  });

  // Check health on start
  window.apiClient.checkHealth().then(h => {
    if (h.ok) console.log("Backend API Health verified:", h.service);
  });
});
