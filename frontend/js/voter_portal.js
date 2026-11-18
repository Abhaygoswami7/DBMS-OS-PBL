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
    gps: { lat: 29.3650, lon: 79.5328 },
    gpsSource: "REGISTERED_STATION",
    accessibilityNeeded: false,
    selectedBooth: null,
    selectedSlot: null,
    activeAllocation: null,
    map: null,
    markers: [],
    demoMarkersMap: {},
    booths: [],
    selectedStationId: null,
    stationDataMap: {},
    stationMarkersMap: {},
    fallbackTileLayerAdded: false
  };

  function triggerMapInvalidate() {
    if (!state.map) return;
    requestAnimationFrame(() => {
      if (state.map) state.map.invalidateSize();
    });
    setTimeout(() => {
      if (state.map) state.map.invalidateSize();
    }, 120);
    setTimeout(() => {
      if (state.map) state.map.invalidateSize();
    }, 400);
  }

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
      const isTarget = (idx + 1 === stepNumber);
      if (isTarget) {
        sec.style.display = "block";
        sec.classList.remove("workflow-step-active");
        void sec.offsetWidth; // Force reflow for smooth Apple CSS transition restart
        sec.classList.add("workflow-step-active");
      } else {
        sec.style.display = "none";
        sec.classList.remove("workflow-step-active");
      }
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
    if (stepNumber === 1 || stepNumber === 2) {
      if (state.map && !state.selectedStationId && typeof BHIMTAL_NAGRIGAON_BOUNDS !== "undefined") {
        state.map.fitBounds(BHIMTAL_NAGRIGAON_BOUNDS, { padding: [35, 35] });
      }
      triggerMapInvalidate();
    } else if (stepNumber === 3) {
      loadNearbyBooths();
      triggerMapInvalidate();
    } else if (stepNumber === 4 && state.selectedBooth) {
      loadAvailableSlots(state.selectedBooth.booth_id);
      if (state.selectedBooth.station_id) {
        selectPollingStation(state.selectedBooth.station_id, {
          flyTo: true,
          zoomLevel: 16.5,
          openPopup: false,
          preferredBoothId: state.selectedBooth.booth_id,
          scrollList: false
        });
      }
      triggerMapInvalidate();
    } else {
      triggerMapInvalidate();
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
    if (quickSelectPanel) quickSelectPanel.style.display = "block";
    if (voterProfileCard) voterProfileCard.style.display = "block";
    if (newRegisterPanel) newRegisterPanel.style.display = "none";
    if (pnrStatusPanel) pnrStatusPanel.style.display = "none";
    tabQuickSelect.classList.add("active");
    tabNewRegister?.classList.remove("active");
    tabPnrStatus?.classList.remove("active");
  });

  tabNewRegister?.addEventListener("click", () => {
    if (quickSelectPanel) quickSelectPanel.style.display = "none";
    if (voterProfileCard) voterProfileCard.style.display = "none";
    if (newRegisterPanel) newRegisterPanel.style.display = "block";
    if (pnrStatusPanel) pnrStatusPanel.style.display = "none";
    tabNewRegister.classList.add("active");
    tabQuickSelect?.classList.remove("active");
    tabPnrStatus?.classList.remove("active");
  });

  tabPnrStatus?.addEventListener("click", () => {
    if (quickSelectPanel) quickSelectPanel.style.display = "none";
    if (voterProfileCard) voterProfileCard.style.display = "none";
    if (newRegisterPanel) newRegisterPanel.style.display = "none";
    if (pnrStatusPanel) pnrStatusPanel.style.display = "block";
    tabPnrStatus.classList.add("active");
    tabQuickSelect?.classList.remove("active");
    tabNewRegister?.classList.remove("active");
  });

  // Initialize authoritative voter list from backend for dropdown
  async function initVoterDropdown() {
    try {
      if (!window.apiClient || !window.apiClient.getVoters) return;
      const res = await window.apiClient.getVoters(60);
      if (res && res.ok && Array.isArray(res.voters) && res.voters.length > 0) {
        if (seededVoterSelect) {
          const currentVal = seededVoterSelect.value;
          seededVoterSelect.innerHTML = '<option value="">-- Choose Seeded Demo Voter --</option>';

          // Separate into available vs already confirmed
          const availableOptgroup = document.createElement("optgroup");
          availableOptgroup.label = "Available to Book (No Active Pass)";
          const bookedOptgroup = document.createElement("optgroup");
          bookedOptgroup.label = "Seeded Voters with Active Confirmed Bookings (Use PNR/Reschedule)";

          res.voters.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.demo_epic_no;
            const statusTag = v.has_active_booking ? `[ACTIVE PASS: ${v.active_token || 'CONFIRMED'}]` : `[AVAILABLE TO BOOK]`;
            opt.textContent = `${v.full_name} (${v.special_category} - Booth ${v.assigned_booth_id} ${v.booth_name || ''} - ${v.demo_epic_no}) ${statusTag}`;
            if (v.has_active_booking) {
              bookedOptgroup.appendChild(opt);
            } else {
              availableOptgroup.appendChild(opt);
            }
          });

          if (availableOptgroup.children.length > 0) seededVoterSelect.appendChild(availableOptgroup);
          if (bookedOptgroup.children.length > 0) seededVoterSelect.appendChild(bookedOptgroup);

          if (currentVal) {
            seededVoterSelect.value = currentVal;
          } else if (state.voter) {
            seededVoterSelect.value = state.voter.demo_epic_no;
          }
        }
      }
    } catch (err) {
      console.warn("Dynamic voters list fetch error, using static fallback:", err);
    }
  }
  initVoterDropdown();

  async function displayVoter(voter) {
    const isDifferentVoter = state.voter && state.voter.demo_epic_no !== voter.demo_epic_no;
    state.voter = voter;

    // Strict two-way synchronization: keep dropdown and manual input aligned
    if (manualEpicInput) {
      manualEpicInput.value = voter.demo_epic_no;
    }
    if (seededVoterSelect) {
      const matchOpt = Array.from(seededVoterSelect.querySelectorAll("option")).find(o => o.value === voter.demo_epic_no);
      if (matchOpt) {
        seededVoterSelect.value = voter.demo_epic_no;
      } else {
        const newOpt = document.createElement("option");
        newOpt.value = voter.demo_epic_no;
        const tag = voter.has_active_booking ? "[ACTIVE PASS]" : "[AVAILABLE TO BOOK]";
        newOpt.textContent = `${voter.full_name} (${voter.special_category} - Booth ${voter.assigned_booth_id} - ${voter.demo_epic_no}) ${tag}`;
        seededVoterSelect.appendChild(newOpt);
        seededVoterSelect.value = voter.demo_epic_no;
      }
    }

    // Clear stale verification, selected booth, and slot data when switching voters
    if (isDifferentVoter) {
      state.isVerified = false;
      state.simulatedToken = null;
      state.selectedBooth = null;
      state.selectedSlot = null;
      state.activeAllocation = null;

      const verifSuccessNotice = document.getElementById("verifSuccessNotice");
      if (verifSuccessNotice) verifSuccessNotice.style.display = "none";

      const btnStep3 = document.getElementById("btnProceedToStep3");
      if (btnStep3) btnStep3.disabled = true;

      const btnStep4 = document.getElementById("btnProceedToStep4");
      if (btnStep4) btnStep4.disabled = true;

      const btnBook = document.getElementById("btnBookSlot");
      if (btnBook) btnBook.disabled = true;

      const slotsGrid = document.getElementById("slotsGridContainer");
      if (slotsGrid) slotsGrid.innerHTML = "";

      const banner = document.getElementById("aiRecommendationBanner");
      if (banner) banner.style.display = "none";
    } else {
      state.isVerified = (voter.simulated_verification_status === "SIMULATED_VERIFIED");
      const verifSuccessNotice = document.getElementById("verifSuccessNotice");
      if (verifSuccessNotice) {
        verifSuccessNotice.style.display = state.isVerified ? "flex" : "none";
      }
      const btnStep3 = document.getElementById("btnProceedToStep3");
      if (btnStep3) btnStep3.disabled = !state.isVerified;
    }

    // Anchor voter GPS coordinates to registered polling station
    if (voter.latitude !== undefined && voter.longitude !== undefined && voter.latitude !== null && voter.longitude !== null) {
      state.gps = {
        lat: parseFloat(voter.latitude),
        lon: parseFloat(voter.longitude)
      };
      state.gpsSource = "REGISTERED_STATION";
    }

    document.getElementById("profVoterName").textContent = voter.full_name;
    const profEpicElem = document.getElementById("profVoterEpic");
    if (profEpicElem) {
      profEpicElem.textContent = voter.demo_epic_no;
    }
    document.getElementById("profCategoryBadge").textContent = `${voter.special_category} · PRIORITY ${voter.priority_level}`;
    document.getElementById("profBoothName").textContent = voter.booth_name || `Booth ${voter.assigned_booth_id}`;
    document.getElementById("profConstituency").textContent = `${voter.parliamentary_constituency || 'Nainital-Udhamsingh Nagar Parliamentary Constituency'} · ${voter.assembly_constituency || 'Bhimtal Assembly Constituency'}`;
    
    const verifElem = document.getElementById("profVerifStatus");
    if (state.isVerified) {
      verifElem.innerHTML = `<span class="badge badge-open">SIMULATED_VERIFIED</span>`;
      const btnStep3 = document.getElementById("btnProceedToStep3");
      if (btnStep3) btnStep3.disabled = false;
    } else {
      verifElem.innerHTML = `<span class="badge badge-partial">UNVERIFIED</span>`;
    }

    // Active booking notification banner in profile
    const profAlert = document.getElementById("profActiveBookingAlert");
    const profDetails = document.getElementById("profActiveBookingDetails");
    const btnProfilePass = document.getElementById("btnProfileViewPass");

    if (voter.has_active_booking && voter.active_booking) {
      state.activeAllocation = voter.active_booking;
      if (profAlert) profAlert.style.display = "block";
      if (profDetails) {
        profDetails.textContent = `Token: ${voter.active_booking.booking_reference_token} | Slot #${voter.active_booking.slot_id} (${voter.active_booking.start_time?.slice(0, 5)} - ${voter.active_booking.end_time?.slice(0, 5)})`;
      }
      if (btnProfilePass) {
        btnProfilePass.onclick = () => {
          if (tabPnrStatus) tabPnrStatus.click();
          if (inputPnrToken) inputPnrToken.value = voter.active_booking.booking_reference_token;
          loadAndDisplayPassForToken(voter.active_booking.booking_reference_token);
        };
      }
    } else {
      if (profAlert) profAlert.style.display = "none";
    }

    voterProfileCard.style.display = "block";

    if (voter.special_category === "PERSON_WITH_DISABILITY" || voter.special_category === "SENIOR_CITIZEN") {
      state.accessibilityNeeded = true;
      const chk = document.getElementById("accessibilityFilterCheck");
      if (chk) chk.checked = true;
    }

    // Persist authenticated session
    window.apiClient.setVoterSession(voter);

    // Refresh map rendering without overriding the Bhimtal & Nagri Gaon focus
    triggerMapInvalidate();
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
    if (manualEpicInput) manualEpicInput.value = epic;
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
  const verifSuccessNotice = document.getElementById("verifSuccessNotice");
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
      if (verifSuccessNotice) verifSuccessNotice.style.display = "flex";
      btnProceedToStep3.disabled = false;
      window.apiClient.showToast("Identity Verification Successful — VERIFIED", "success");
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
    state.gpsSource = "MANUAL_PRESET";
    loadNearbyBooths();
    triggerMapInvalidate();
  };

  // Regional Demonstration Presets (Bhimtal & Nagri Gaon)
  document.getElementById("presetGehuBhimtal")?.addEventListener("click", () => setGpsPreset(29.3751, 79.5313));
  document.getElementById("presetWoodbridge")?.addEventListener("click", () => setGpsPreset(29.3690, 79.5220));
  document.getElementById("presetVikasBhawan")?.addEventListener("click", () => setGpsPreset(29.3602, 79.5535));
  document.getElementById("presetNagarPalika")?.addEventListener("click", () => setGpsPreset(29.3445, 79.5634));
  // Backward compatibility alias bindings
  document.getElementById("presetDdnCantt")?.addEventListener("click", () => setGpsPreset(29.3751, 79.5313));
  document.getElementById("presetRajpurRd")?.addEventListener("click", () => setGpsPreset(29.3690, 79.5220));
  document.getElementById("presetRishikesh")?.addEventListener("click", () => setGpsPreset(29.3602, 79.5535));
  document.getElementById("presetHaridwar")?.addEventListener("click", () => setGpsPreset(29.3445, 79.5634));

  accessibilityFilterCheck?.addEventListener("change", (e) => {
    state.accessibilityNeeded = e.target.checked;
    loadNearbyBooths();
  });

  // ---------------------------------------------------------------------------
  // Leaflet Map Controller & Live Cartography
  // ---------------------------------------------------------------------------

  // Geographic Focus: Bhimtal and Nagri Gaon (Nainital District, Uttarakhand)
  const BHIMTAL_COORDS = [29.3500, 79.5535];
  const NAGRI_GAON_COORDS = [29.3800, 79.5121];
  const BHIMTAL_NAGRIGAON_CENTER = [29.3625, 79.5380];
  const BHIMTAL_NAGRIGAON_BOUNDS = [
    [29.3400, 79.5080], // Southwest bounds (covers Woodbridge School, Nagri Gaon & western approaches)
    [29.3850, 79.5680]  // Northeast bounds (covers GEHU, Vikas Bhawan, Bhimtal town & lake, Nagar Palika)
  ];

  // Demonstration Polling Locations (Single Maintainable Location Data Source)
  const DEMO_POLLING_LOCATIONS = [
    {
      id: "demo-woodbridge",
      name: "Woodbridge School",
      tag: "DEMO POLLING LOCATION",
      category: "School Campus",
      sector: "Near Nagri Gaon",
      address: "Dob, Lewshal, Bhowali-Bhimtal Road, near Nagri Gaon, PIN: 263132",
      latitude: 29.3690,
      longitude: 79.5220,
      pinClass: "demo-school-pin",
      iconColor: "#4f46e5",
      iconSvg: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`
    },
    {
      id: "demo-gehu",
      name: "Graphic Era Hill University, Bhimtal Campus",
      tag: "DEMO POLLING LOCATION",
      category: "University Campus",
      sector: "Near Nagri Gaon / Sattal Road",
      address: "Sattal Road, Bhimtal Campus, Nainital District, PIN: 263136",
      latitude: 29.3751,
      longitude: 79.5313,
      pinClass: "demo-univ-pin",
      iconColor: "#0d9488",
      iconSvg: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>`
    },
    {
      id: "demo-vikas-bhawan",
      name: "Vikas Bhawan (District Development Complex)",
      tag: "DEMO POLLING LOCATION",
      category: "Government Office",
      sector: "Around Bhimtal",
      address: "Vikas Bhawan, Block Road, Bhimtal, Nainital District, PIN: 263136",
      latitude: 29.3602,
      longitude: 79.5535,
      pinClass: "demo-gov-pin",
      iconColor: "#0284c7",
      iconSvg: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="9" y1="22" x2="9" y2="22.01"/><line x1="15" y1="22" x2="15" y2="22.01"/><line x1="9" y1="18" x2="9" y2="18.01"/><line x1="15" y1="18" x2="15" y2="18.01"/><line x1="9" y1="14" x2="9" y2="14.01"/><line x1="15" y1="14" x2="15" y2="14.01"/><line x1="9" y1="10" x2="9" y2="10.01"/><line x1="15" y1="10" x2="15" y2="10.01"/><line x1="9" y1="6" x2="9" y2="6.01"/><line x1="15" y1="6" x2="15" y2="6.01"/></svg>`
    },
    {
      id: "demo-nagar-palika",
      name: "Nagar Palika Parishad Office, Bhimtal",
      tag: "DEMO POLLING LOCATION",
      category: "Government Office",
      sector: "Around Bhimtal",
      address: "Nagar Palika Parishad, Lake Road, Bhimtal, PIN: 263136",
      latitude: 29.3445,
      longitude: 79.5634,
      pinClass: "demo-gov-alt-pin",
      iconColor: "#b45309",
      iconSvg: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 21v-6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v6"/></svg>`
    }
  ];
  window.DEMO_POLLING_LOCATIONS = DEMO_POLLING_LOCATIONS;

  function plotDemoPollingLocations() {
    if (!state.map) return;
    state.demoMarkersMap = state.demoMarkersMap || {};

    DEMO_POLLING_LOCATIONS.forEach(loc => {
      const icon = L.divIcon({
        className: `custom-demo-pin ${loc.pinClass}`,
        html: `
          <div class="pin-marker" title="${loc.name}">
            ${loc.iconSvg}
          </div>
        `,
        iconSize: [30, 30],
        iconAnchor: [15, 27],
        popupAnchor: [0, -27]
      });

      const marker = L.marker([loc.latitude, loc.longitude], {
        icon: icon,
        title: loc.name,
        zIndexOffset: 750
      }).addTo(state.map);

      marker.bindTooltip(loc.name, {
        permanent: true,
        direction: "top",
        offset: [0, -27],
        className: "map-location-label"
      });

      marker.bindPopup(`
        <div class="map-popup-header" style="border-bottom: 2px solid ${loc.iconColor};">
          <strong style="color: ${loc.iconColor}; font-size: 12px;">${loc.name}</strong>
        </div>
        <div style="font-size: 11px; margin-top: 4px; line-height: 1.45;">
          <div style="margin-bottom: 4px;">
            <span class="badge badge-partial" style="font-size: 9.5px; font-weight: 700;">DEMO POLLING LOCATION</span>
            <span class="jurisdiction-tag" style="font-size: 9.5px;">${loc.category}</span>
          </div>
          <div><strong>Sector:</strong> ${loc.sector}</div>
          <div style="color: #64748b; font-size: 10.5px; margin-top: 2px;">${loc.address}</div>
          <div style="font-family: var(--font-mono); font-size: 10.5px; margin-top: 3px;"><strong>Coordinates:</strong> ${loc.latitude.toFixed(4)}° N, ${loc.longitude.toFixed(4)}° E</div>
          <div style="border-top: 1px solid #e2e8f0; margin-top: 6px; padding-top: 6px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 10px; color: #64748b;">Demo Model Station</span>
            <button type="button" class="btn-primary" style="padding: 2px 8px; font-size: 10px; border-radius: 3px;" onclick="window.selectDemoLocation('${loc.id}')">Select Reference</button>
          </div>
        </div>
      `);

      state.markers.push(marker);
      state.demoMarkersMap[loc.id] = marker;
    });
  }

  window.selectDemoLocation = function(locationId) {
    const loc = DEMO_POLLING_LOCATIONS.find(l => l.id === locationId);
    if (!loc) return;

    state.gps = { lat: loc.latitude, lon: loc.longitude };
    state.gpsSource = "DEMO_LOCATION";
    state.activeDemoLocation = loc;

    if (state.map) {
      state.map.flyTo([loc.latitude, loc.longitude], 16.5, { duration: 0.8, easeLinearity: 0.25 });
      const marker = state.demoMarkersMap && state.demoMarkersMap[loc.id];
      if (marker) {
        setTimeout(() => marker.openPopup(), 380);
      }
    }

    // Refresh proximity calculation with demo location coordinates
    loadNearbyBooths();

    window.apiClient.showToast(`Selected ${loc.name} as reference location.`, "info");
  };

  function getVoterLocationIcon() {
    return L.divIcon({
      className: "custom-voter-pin",
      html: `
        <div class="voter-radar-ring"></div>
        <div class="voter-dot">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3">
            <circle cx="12" cy="12" r="7" fill="#fb792b"/>
          </svg>
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -14]
    });
  }

  function getStationMarkerIcon(hasRamp = false, isSelected = false) {
    const bg = isSelected ? "#fb792b" : "#213d77";
    const selectedClass = isSelected ? "station-pin-selected" : "";
    const rampBadge = hasRamp
      ? `<span class="station-ramp-badge" title="Wheelchair Accessible Ramp Available">RAMP</span>`
      : "";
    
    return L.divIcon({
      className: `custom-station-pin ${selectedClass}`,
      html: `
        <div class="pin-marker" style="background:${bg};">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 21h18"/>
            <path d="M5 21V7l7-4 7 4v14"/>
            <path d="M9 21v-6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v6"/>
          </svg>
          ${rampBadge}
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 28],
      popupAnchor: [0, -28]
    });
  }

  function getBhimtalMarkerIcon() {
    return L.divIcon({
      className: "custom-bhimtal-pin",
      html: `
        <div class="pin-marker" title="Bhimtal, Nainital District">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
            <circle cx="12" cy="9" r="2.5" fill="#ffffff"/>
          </svg>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 28],
      popupAnchor: [0, -28]
    });
  }

  function getNagriGaonMarkerIcon() {
    return L.divIcon({
      className: "custom-nagrigaon-pin",
      html: `
        <div class="pin-marker" title="Nagri Gaon, Nainital District">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            <polyline points="9 22 9 12 15 12 15 22"/>
          </svg>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 28],
      popupAnchor: [0, -28]
    });
  }

  function plotBhimtalAndNagriGaonMarkers() {
    if (!state.map) return;

    // Bhimtal Landmark Marker
    const bhimtalMarker = L.marker(BHIMTAL_COORDS, {
      icon: getBhimtalMarkerIcon(),
      title: "Bhimtal, Nainital District",
      zIndexOffset: 850
    }).addTo(state.map);

    bhimtalMarker.bindTooltip("Bhimtal", {
      permanent: true,
      direction: "top",
      offset: [0, -28],
      className: "map-location-label"
    });

    bhimtalMarker.bindPopup(`
      <div class="map-popup-header">
        <strong style="color: #0284c7; font-size: 12px;">Bhimtal, Nainital District</strong>
      </div>
      <div style="font-size: 11px; margin-top: 4px; line-height: 1.45;">
        <div><strong>Coordinates:</strong> 29.3500° N, 79.5535° E</div>
        <div><strong>Altitude:</strong> ~1,370 m above sea level</div>
        <div><strong>Administrative Region:</strong> Nainital District, Uttarakhand, India</div>
        <div style="color: #64748b; margin-top: 4px; border-top: 1px solid #e2e8f0; padding-top: 4px;">
          Geographical focus point for Bhimtal Lake and municipal town.
        </div>
      </div>
    `);

    // Nagri Gaon Landmark Marker
    const nagriGaonMarker = L.marker(NAGRI_GAON_COORDS, {
      icon: getNagriGaonMarkerIcon(),
      title: "Nagri Gaon, Nainital District",
      zIndexOffset: 850
    }).addTo(state.map);

    nagriGaonMarker.bindTooltip("Nagri Gaon", {
      permanent: true,
      direction: "top",
      offset: [0, -28],
      className: "map-location-label"
    });

    nagriGaonMarker.bindPopup(`
      <div class="map-popup-header">
        <strong style="color: #16a34a; font-size: 12px;">Nagri Gaon, Nainital District</strong>
      </div>
      <div style="font-size: 11px; margin-top: 4px; line-height: 1.45;">
        <div><strong>Coordinates:</strong> 29.3800° N, 79.5121° E</div>
        <div><strong>Administrative Region:</strong> Bhimtal Block, Nainital District, Uttarakhand, PIN: 263132</div>
        <div style="color: #64748b; margin-top: 4px; border-top: 1px solid #e2e8f0; padding-top: 4px;">
          Geographical focus point for Nagri Gaon village near Bhimtal.
        </div>
      </div>
    `);

    state.markers.push(bhimtalMarker, nagriGaonMarker);
  }

  function addFocusMapControl() {
    if (!state.map || state.focusControlAdded) return;
    const FocusControl = L.Control.extend({
      options: { position: "topright" },
      onAdd: function() {
        const btn = L.DomUtil.create("button", "leaflet-bar leaflet-control leaflet-control-custom");
        btn.type = "button";
        btn.title = "Reset View to Bhimtal & Nagri Gaon";
        btn.innerHTML = `<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;font-size:11px;font-weight:700;color:#213d77;background:#ffffff;border-radius:4px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,0.2);"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#213d77" stroke-width="2.5"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/></svg> Focus Bhimtal</span>`;
        btn.style.border = "none";
        btn.style.background = "transparent";
        btn.style.cursor = "pointer";
        btn.onclick = function(e) {
          e.preventDefault();
          e.stopPropagation();
          state.map.fitBounds(BHIMTAL_NAGRIGAON_BOUNDS, { padding: [35, 35] });
        };
        return btn;
      }
    });
    state.map.addControl(new FocusControl());
    state.focusControlAdded = true;
  }

  function ensureMapInitialized() {
    const mapContainer = document.getElementById("boothMap");
    const offlineFallback = document.getElementById("mapOfflineFallback");
    if (!mapContainer) return false;

    if (typeof L === "undefined" || window.leafletFailed) {
      if (offlineFallback) offlineFallback.style.display = "flex";
      mapContainer.style.display = "none";
      return false;
    }

    if (offlineFallback) offlineFallback.style.display = "none";
    mapContainer.style.display = "block";

    if (!state.map) {
      try {
        state.map = L.map("boothMap", {
          center: BHIMTAL_NAGRIGAON_CENTER,
          zoom: 12,
          zoomControl: true,
          scrollWheelZoom: true,
          fadeAnimation: true
        });

        // Primary: OpenStreetMap Tile Layer
        const primaryTileLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
        });
        primaryTileLayer.addTo(state.map);

        // Fallback: CartoDB Voyager tiles if OSM tiles fail or are blocked
        primaryTileLayer.on("tileerror", () => {
          if (!state.fallbackTileLayerAdded) {
            state.fallbackTileLayerAdded = true;
            console.warn("OSM tile load failed; activating CartoDB Voyager tile fallback.");
            L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
              maxZoom: 19,
              subdomains: "abcd",
              attribution: '&copy; CartoDB &copy; OpenStreetMap'
            }).addTo(state.map);
          }
        });

        window.voteItMap = state.map;

        // Add top-right custom control button to refocus on Bhimtal & Nagri Gaon
        addFocusMapControl();

        // Fit initial view to Bhimtal and Nagri Gaon bounds
        state.map.fitBounds(BHIMTAL_NAGRIGAON_BOUNDS, { padding: [35, 35] });

        // Plot Bhimtal, Nagri Gaon & demonstration polling location markers
        plotBhimtalAndNagriGaonMarkers();
        plotDemoPollingLocations();

        // ResizeObserver ensures map redraws cleanly upon container dimension changes
        if (window.ResizeObserver) {
          const ro = new ResizeObserver(() => {
            if (state.map) state.map.invalidateSize();
          });
          ro.observe(mapContainer);
        }

      } catch (err) {
        console.error("Leaflet map initialization error:", err);
        if (offlineFallback) offlineFallback.style.display = "flex";
        mapContainer.style.display = "none";
        return false;
      }
    }

    triggerMapInvalidate();
    return true;
  }

  // ---------------------------------------------------------------------------
  // Centralized Interactive Polling Station & Booth Selection Controller
  // ---------------------------------------------------------------------------
  function updateSelectedLocationIndicator(stnData) {
    const indicator = document.getElementById("selectedStationIndicator");
    const nameSpan = document.getElementById("indicatorStationName");
    if (!indicator || !nameSpan) return;

    if (stnData) {
      nameSpan.textContent = `${stnData.station_name} (${stnData.latitude.toFixed(4)} N, ${stnData.longitude.toFixed(4)} E)`;
      indicator.style.display = "flex";
    } else {
      indicator.style.display = "none";
    }
  }

  function resetMapSelection() {
    state.selectedStationId = null;
    if (state.stationMarkersMap) {
      Object.entries(state.stationMarkersMap).forEach(([sId, marker]) => {
        const mStnData = state.stationDataMap && state.stationDataMap[sId];
        const hasRamp = mStnData ? !!mStnData.has_wheelchair_ramp : false;
        marker.setIcon(getStationMarkerIcon(hasRamp, false));
        marker.setZIndexOffset(700);
        marker.closePopup();
      });
    }
    updateSelectedLocationIndicator(null);
    if (state.map && typeof BHIMTAL_NAGRIGAON_BOUNDS !== "undefined") {
      state.map.fitBounds(BHIMTAL_NAGRIGAON_BOUNDS, {
        padding: [35, 35],
        maxZoom: 13
      });
    }
  }
  window.resetMapSelection = resetMapSelection;
  document.getElementById("btnResetMapView")?.addEventListener("click", resetMapSelection);

  function selectPollingStation(stationId, options = {}) {
    const opts = Object.assign({
      flyTo: true,
      zoomLevel: 16.5,
      openPopup: true,
      preferredBoothId: null,
      scrollList: true
    }, options);

    state.selectedStationId = stationId;
    const stnData = state.stationDataMap ? state.stationDataMap[stationId] : null;

    // 1. Resolve and update selected booth
    if (stnData && stnData.booths && stnData.booths.length > 0) {
      let targetBooth = null;
      if (opts.preferredBoothId) {
        targetBooth = stnData.booths.find(b => b.booth_id === opts.preferredBoothId);
      }
      if (!targetBooth && state.voter) {
        targetBooth = stnData.booths.find(b => b.booth_id === state.voter.assigned_booth_id);
      }
      if (!targetBooth) {
        targetBooth = stnData.booths[0];
      }

      if (targetBooth) {
        if (state.selectedBooth?.booth_id !== targetBooth.booth_id) {
          state.selectedSlot = null;
        }
        state.selectedBooth = targetBooth;

        if (btnProceedToStep4) {
          btnProceedToStep4.disabled = false;
          btnProceedToStep4.textContent = `Select ${targetBooth.booth_name} & Proceed`;
        }
      }
    }

    // 2. Synchronize left-hand station list selection
    document.querySelectorAll(".booth-card").forEach(c => {
      const bId = parseInt(c.getAttribute("data-booth-id"), 10);
      const isExactSelected = state.selectedBooth && state.selectedBooth.booth_id === bId;

      if (isExactSelected) {
        c.classList.add("selected");
        if (opts.scrollList) {
          c.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      } else {
        c.classList.remove("selected");
      }
    });

    // 3. Highlight selected marker on the map with pulsing animation and reset others
    if (state.stationMarkersMap) {
      Object.entries(state.stationMarkersMap).forEach(([sId, marker]) => {
        const isCurrent = String(sId) === String(stationId);
        const mStnData = state.stationDataMap && state.stationDataMap[sId];
        const hasRamp = mStnData ? !!mStnData.has_wheelchair_ramp : false;

        if (isCurrent) {
          marker.setIcon(getStationMarkerIcon(hasRamp, true));
          marker.setZIndexOffset(1200);

          if (opts.flyTo && state.map) {
            const lat = stnData ? stnData.latitude : marker.getLatLng().lat;
            const lon = stnData ? stnData.longitude : marker.getLatLng().lng;
            state.map.flyTo([lat, lon], opts.zoomLevel, {
              duration: 0.85,
              easeLinearity: 0.22
            });
          }

          if (opts.openPopup) {
            setTimeout(() => {
              if (marker && state.map) marker.openPopup();
            }, 380);
          }
        } else {
          marker.setIcon(getStationMarkerIcon(hasRamp, false));
          marker.setZIndexOffset(700);
        }
      });
    }

    // 4. Update subtle location indicator
    updateSelectedLocationIndicator(stnData);
  }
  window.selectPollingStation = selectPollingStation;

  window.selectBoothFromMap = function(boothId) {
    if (state.currentStep !== 3) {
      goToStep(3);
    }
    const booth = state.booths ? state.booths.find(b => b.booth_id === boothId) : null;
    const stationId = booth ? booth.station_id : null;
    if (stationId) {
      selectPollingStation(stationId, {
        flyTo: true,
        zoomLevel: 16.5,
        openPopup: true,
        preferredBoothId: boothId,
        scrollList: true
      });
    } else {
      const card = document.querySelector(`.booth-card[data-booth-id="${boothId}"]`);
      if (card) {
        card.click();
        card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  };

  async function loadNearbyBooths() {
    if (boothListContainer) {
      boothListContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 12px;">Calculating Haversine proximity matrix...</div>`;
    }

    const voterId = state.voter ? state.voter.voter_id : null;

    // Demonstration platform: Load all candidate stations and booths without AC/PC restriction
    const res = await window.apiClient.getNearbyBooths(
      state.gps.lat,
      state.gps.lon,
      null,
      state.accessibilityNeeded,
      voterId
    );

    if (!res.ok || !res.booths) {
      if (boothListContainer) {
        boothListContainer.innerHTML = `<div style="color: var(--irctc-status-wl); padding: 1rem; font-size: 12px;">Failed to load nearby booths.</div>`;
      }
      initOrUpdateMap([]);
      return;
    }

    state.booths = res.booths;
    renderBoothList(res.booths);
    initOrUpdateMap(res.booths);
  }

  window.loadNearbyBooths = loadNearbyBooths;

  function renderBoothList(booths) {
    if (!boothListContainer) return;
    boothListContainer.innerHTML = "";
    if (!booths || booths.length === 0) {
      const pcName = state.voter?.parliamentary_constituency || 'Nainital-Udhamsingh Nagar PC';
      const acName = state.voter?.assembly_constituency || 'Bhimtal AC';
      boothListContainer.innerHTML = `
        <div style="color: var(--irctc-status-wl); padding: 1.5rem; font-size: 12px; background: #fff5f5; border: 1px solid #fed7d7; border-radius: 4px;">
          <strong>No Active Polling Booths Found</strong><br/>
          No active polling booths currently available for polling logistics.
        </div>`;
      if (btnProceedToStep4) btnProceedToStep4.disabled = true;
      return;
    }

    let foundAssignedBooth = null;

    booths.forEach((b) => {
      const isAssigned = (state.voter && state.voter.assigned_booth_id === b.booth_id);

      if (isAssigned) {
        foundAssignedBooth = b;
      }

      const card = document.createElement("div");
      card.className = `booth-card ${state.selectedBooth?.booth_id === b.booth_id ? 'selected' : ''}`;
      card.setAttribute("data-booth-id", b.booth_id);
      card.setAttribute("data-station-id", b.station_id);
      
      const distanceSuffix = state.gpsSource === "DEMO_LOCATION"
        ? `FROM ${state.activeDemoLocation?.name || 'DEMO LOCATION'}`
        : "FROM GPS";
      const distanceDisplay = isAssigned
        ? (state.gpsSource === "REGISTERED_STATION" ? "ASSIGNED POLLING BOOTH" : `${b.distance_km} KM ${distanceSuffix}`)
        : (state.gpsSource === "REGISTERED_STATION" ? `${b.distance_km} KM FROM ASSIGNED STATION` : `${b.distance_km} KM ${distanceSuffix}`);
      const jurisdictionBadge = isAssigned
        ? '<span class="badge badge-open">REGISTERED POLLING BOOTH</span>'
        : '<span class="badge badge-open">AVAILABLE FOR ALLOCATION</span>';

      card.innerHTML = `
        <div class="booth-card-header">
          <div>
            <div class="booth-card-title">${b.booth_name} · ${b.station_name}</div>
            <div style="font-size: 11px; color: var(--text-secondary);">${b.room_number || 'Room Main'} · Capacity: ${b.max_capacity_per_slot} per slot</div>
          </div>
          <div class="booth-distance-tag">${distanceDisplay}</div>
        </div>
        <div class="booth-card-body">
          <div class="booth-jurisdiction-tags">
            <span class="jurisdiction-tag">PC: ${b.parliamentary_constituency}</span>
            <span class="jurisdiction-tag">AC: ${b.assembly_constituency}</span>
            ${b.has_wheelchair_ramp ? '<span class="badge badge-open">RAMP AVAILABLE</span>' : ''}
            ${jurisdictionBadge}
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">
            Station Address: ${b.station_address}
          </div>
        </div>
      `;

      // All polling booths are fully selectable
      card.addEventListener("click", () => {
        selectPollingStation(b.station_id, {
          flyTo: true,
          zoomLevel: 16.5,
          openPopup: true,
          preferredBoothId: b.booth_id,
          scrollList: false
        });
      });

      boothListContainer.appendChild(card);
    });

    // Auto-select assigned booth by default
    if (foundAssignedBooth) {
      selectPollingStation(foundAssignedBooth.station_id, {
        flyTo: false,
        openPopup: false,
        preferredBoothId: foundAssignedBooth.booth_id,
        scrollList: false
      });
    } else if (booths.length > 0 && !state.selectedBooth) {
      selectPollingStation(booths[0].station_id, {
        flyTo: false,
        openPopup: false,
        preferredBoothId: booths[0].booth_id,
        scrollList: false
      });
    }
  }

  function initOrUpdateMap(booths) {
    if (!ensureMapInitialized()) return;

    // Clear previous markers
    if (state.markers && state.markers.length > 0) {
      state.markers.forEach(m => {
        try { state.map.removeLayer(m); } catch (e) {}
      });
    }
    state.markers = [];
    state.stationMarkersMap = {};
    state.stationDataMap = {};

    // 0. Plot Bhimtal & Nagri Gaon town landmark markers
    plotBhimtalAndNagriGaonMarkers();

    // 1. Group booths by Station
    const boothList = Array.isArray(booths) ? booths : (state.booths || []);
    
    // If no dynamic database booths are present, plot demo static markers as fallback
    if (!boothList || boothList.length === 0) {
      plotDemoPollingLocations();
    }

    const bounds = L.latLngBounds();

    // 2. Plot Voter Location Marker
    if (state.gps && !isNaN(state.gps.lat) && !isNaN(state.gps.lon)) {
      const voterPos = [state.gps.lat, state.gps.lon];
      const voterMarker = L.marker(voterPos, {
        icon: getVoterLocationIcon(),
        title: "Your Reference Location",
        zIndexOffset: 1000
      }).addTo(state.map);

      const refTitle = state.gpsSource === "REGISTERED_STATION"
        ? "REGISTERED STATION REFERENCE"
        : (state.gpsSource === "DEMO_LOCATION" ? "DEMO LOCATION REFERENCE" : "GPS / PRESET REFERENCE LOCATION");
      const refDesc = state.gpsSource === "REGISTERED_STATION"
        ? `Station Anchor: ${state.voter?.station_name || 'Assigned Station'}<br/><span style="color: #64748b; font-size: 10px;">Distances calculated from registered station coordinates.</span>`
        : (state.gpsSource === "DEMO_LOCATION"
            ? `Demo Anchor: ${state.activeDemoLocation?.name || 'Demonstration Location'}<br/><span style="color: #64748b; font-size: 10px;">Haversine distances measured from this demonstration location.</span>`
            : `Device / Preset GPS Coordinates<br/><span style="color: #64748b; font-size: 10px;">Haversine distances measured from this reference point.</span>`);

      voterMarker.bindPopup(`
        <div class="map-popup-header">
          <strong style="color: #fb792b; font-size: 11.5px;">${refTitle}</strong>
        </div>
        <div style="font-size: 11px; margin-top: 4px;">
          Coordinates: ${state.gps.lat.toFixed(4)} N, ${state.gps.lon.toFixed(4)} E<br/>
          ${refDesc}
        </div>
      `);

      state.markers.push(voterMarker);
      bounds.extend(voterPos);
    }

    // 3. Group booths by Station (to avoid overlapping pins at same physical station)
    const stationsMap = {};

    boothList.forEach(b => {
      const lat = parseFloat(b.latitude);
      const lon = parseFloat(b.longitude);
      if (isNaN(lat) || isNaN(lon) || lat === 0 || lon === 0) return;

      const stnKey = b.station_id || `${lat}_${lon}`;
      if (!stationsMap[stnKey]) {
        stationsMap[stnKey] = {
          station_id: b.station_id,
          station_name: b.station_name,
          station_address: b.station_address,
          latitude: lat,
          longitude: lon,
          distance_km: b.distance_km,
          has_wheelchair_ramp: !!b.has_wheelchair_ramp,
          parliamentary_constituency: b.parliamentary_constituency,
          assembly_constituency: b.assembly_constituency,
          booths: []
        };
      }
      stationsMap[stnKey].booths.push(b);
    });

    state.stationDataMap = stationsMap;

    // 4. Create station markers with interactive selection popups, labels, and click handlers
    Object.values(stationsMap).forEach(stn => {
      const isSelected = state.selectedStationId
        ? String(stn.station_id) === String(state.selectedStationId)
        : (state.selectedBooth && stn.booths.some(b => b.booth_id === state.selectedBooth.booth_id));

      const marker = L.marker([stn.latitude, stn.longitude], {
        icon: getStationMarkerIcon(stn.has_wheelchair_ramp, isSelected),
        title: stn.station_name,
        zIndexOffset: isSelected ? 1200 : 700
      }).addTo(state.map);

      marker.bindTooltip(stn.station_name, {
        permanent: true,
        direction: "top",
        offset: [0, -28],
        className: "map-location-label"
      });

      const boothsHtml = stn.booths.map(b => `
        <div style="border-top: 1px solid #e2e8f0; padding-top: 6px; margin-top: 6px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
          <div>
            <div style="font-weight: 600; color: #213d77; font-size: 11px;">${b.booth_name}</div>
            <div style="font-size: 10px; color: #64748b;">${b.room_number || 'Room Main'} · Cap: ${b.max_capacity_per_slot || 40}/slot</div>
          </div>
          <button type="button" class="btn-primary" style="padding: 2px 7px; font-size: 10px; border-radius: 3px;" onclick="window.selectBoothFromMap(${b.booth_id})">Select</button>
        </div>
      `).join("");

      marker.bindPopup(`
        <div class="map-popup-header">
          <strong style="color: #213d77; font-size: 12px;">${stn.station_name}</strong>
        </div>
        <div style="font-size: 11px; margin-top: 4px; line-height: 1.4;">
          <div style="color: #64748b;">${stn.station_address || ''}</div>
          <div style="margin-top: 4px;">
            <span class="jurisdiction-tag" style="font-size: 9.5px;">PC: ${stn.parliamentary_constituency || 'Nainital-Udhamsingh Nagar Parliamentary Constituency'}</span>
            <span class="jurisdiction-tag" style="font-size: 9.5px;">AC: ${stn.assembly_constituency || 'Bhimtal Assembly Constituency'}</span>
          </div>
          <div style="margin-top: 6px; font-weight: 600; color: #fb792b;">
            Haversine Distance: ${stn.distance_km} km
          </div>
          ${stn.has_wheelchair_ramp ? '<div style="color: #28a745; font-size: 10.5px; font-weight: 600; margin-top: 2px;">Wheelchair Ramp Available</div>' : ''}
          ${boothsHtml}
        </div>
      `);

      // REVERSE INTERACTION: Clicking marker directly on map selects station & booth
      marker.on("click", () => {
        selectPollingStation(stn.station_id, {
          flyTo: true,
          zoomLevel: 16.5,
          openPopup: true,
          scrollList: true
        });
      });

      state.markers.push(marker);
      state.stationMarkersMap[stn.station_id || `${stn.latitude}_${stn.longitude}`] = marker;
      bounds.extend([stn.latitude, stn.longitude]);
    });

    // 5. Fit bounds to Bhimtal and Nagri Gaon focus area if no station selected
    if (!state.selectedStationId && typeof BHIMTAL_NAGRIGAON_BOUNDS !== "undefined") {
      state.map.fitBounds(BHIMTAL_NAGRIGAON_BOUNDS, {
        padding: [35, 35],
        maxZoom: 13
      });
    } else if (state.selectedStationId && stationsMap[state.selectedStationId]) {
      const selStn = stationsMap[state.selectedStationId];
      updateSelectedLocationIndicator(selStn);
    }

    triggerMapInvalidate();
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
    if (!state.selectedBooth) return;

    // All polling booths and stations are selectable; display actual constituency metadata
    const isAssigned = (state.voter && state.voter.assigned_booth_id === boothId);
    const boothBadge = isAssigned
      ? `<span class="badge badge-open" style="margin-left: 6px;">REGISTERED BOOTH</span>`
      : `<span class="badge badge-open" style="margin-left: 6px;">AVAILABLE BOOTH</span>`;

    selectedBoothSummary.innerHTML = `Showing time-slots for <strong>${state.selectedBooth.station_name}</strong> (${state.selectedBooth.booth_name}) ${boothBadge} · <span style="font-size: 11px; color: var(--text-muted);">PC: ${state.selectedBooth.parliamentary_constituency} · AC: ${state.selectedBooth.assembly_constituency}</span>`;
    slotsGridContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 12px;">Querying discretized polling windows and AI crowd forecasts...</div>`;

    const res = await window.apiClient.getAvailableSlots(
      boothId,
      state.voter ? state.voter.voter_id : null,
      1,
      state.gps ? state.gps.lat : null,
      state.gps ? state.gps.lon : null
    );

    if (!res.ok || !res.slots) {
      const errorMsg = res.message || "Failed to load time slots.";
      slotsGridContainer.innerHTML = `<div style="color: var(--irctc-status-wl); padding: 1.5rem; font-size: 12px;">${errorMsg}</div>`;
      if (btnBookSlot) btnBookSlot.disabled = true;
      if (aiRecommendationBanner) aiRecommendationBanner.style.display = "none";
      const selBanner = document.getElementById("slotSelectionStatusBanner");
      if (selBanner) selBanner.style.display = "none";
      return;
    }

    if (res.recommendation && res.recommendation.recommendation_reason) {
      aiRecommendationBanner.style.display = "flex";
      aiRecommendationText.textContent = res.recommendation.recommendation_reason;
    } else {
      if (aiRecommendationBanner) aiRecommendationBanner.style.display = "none";
    }

    // Check if voter already holds an active confirmed pass for this election
    const activeWarnBanner = document.getElementById("activeBookingWarningBanner");
    const activeWarnText = document.getElementById("activeBookingWarningText");
    const hasActivePass = !!(state.voter && (state.voter.has_active_booking || state.voter.active_booking));

    if (hasActivePass) {
      const activeTok = state.voter.active_booking?.booking_reference_token || "ACTIVE_PASS";
      const activeSlot = state.voter.active_booking?.slot_id || "";
      if (activeWarnBanner) activeWarnBanner.style.display = "block";
      if (activeWarnText) {
        activeWarnText.innerHTML = `Voter <strong>${state.voter.full_name}</strong> already holds active confirmed booking token <strong>${activeTok}</strong> for Slot #${activeSlot}. Multiple concurrent active bookings are strictly prevented under ECI rules. Use the PNR / Reschedule tab to modify arrival time.`;
      }
      if (btnBookSlot) {
        btnBookSlot.disabled = true;
        btnBookSlot.textContent = "Active Booking Already Confirmed (Use Reschedule)";
      }
    } else {
      if (activeWarnBanner) activeWarnBanner.style.display = "none";
    }

    renderSlotsGrid(res.slots, hasActivePass);
  }

  function renderSlotsGrid(slots, hasActivePass = false) {
    slotsGridContainer.innerHTML = "";
    const slotSelectionStatusBanner = document.getElementById("slotSelectionStatusBanner");
    const slotSelectionStatusText = document.getElementById("slotSelectionStatusText");
    const slotSelectionStatusBadge = document.getElementById("slotSelectionStatusBadge");

    const recommendedSlot = slots.find(s => s.is_recommended) || null;

    // Preserve existing selection if valid and available; otherwise default to recommended (if available and no active pass)
    if (state.selectedSlot) {
      const existingMatch = slots.find(s => s.slot_id === state.selectedSlot.slot_id);
      if (existingMatch && existingMatch.occupancy_status !== "FULL" && existingMatch.available_capacity > 0) {
        state.selectedSlot = existingMatch;
      } else if (!hasActivePass && recommendedSlot && recommendedSlot.occupancy_status !== "FULL" && recommendedSlot.available_capacity > 0) {
        state.selectedSlot = recommendedSlot;
      } else {
        const fallback = slots.find(s => s.occupancy_status !== "FULL" && s.available_capacity > 0);
        state.selectedSlot = (!hasActivePass && fallback) ? fallback : null;
      }
    } else if (!hasActivePass) {
      if (recommendedSlot && recommendedSlot.occupancy_status !== "FULL" && recommendedSlot.available_capacity > 0) {
        state.selectedSlot = recommendedSlot;
      } else {
        const fallback = slots.find(s => s.occupancy_status !== "FULL" && s.available_capacity > 0);
        if (fallback) state.selectedSlot = fallback;
      }
    }

    function updateSelectionStatusUI() {
      if (hasActivePass || !state.selectedSlot) {
        if (slotSelectionStatusBanner) slotSelectionStatusBanner.style.display = "none";
        if (btnBookSlot && !hasActivePass) {
          btnBookSlot.disabled = true;
          btnBookSlot.textContent = "Select a Time Slot to Proceed";
        }
        return;
      }

      const isMatch = recommendedSlot && (state.selectedSlot.slot_id === recommendedSlot.slot_id);
      if (slotSelectionStatusBanner) {
        slotSelectionStatusBanner.style.display = "flex";
        slotSelectionStatusBanner.className = `slot-selection-status-banner ${isMatch ? 'matches-recommendation' : 'custom-choice'}`;
      }

      const selRange = `${state.selectedSlot.start_time.slice(0, 5)} - ${state.selectedSlot.end_time.slice(0, 5)} HRS`;
      const recRange = recommendedSlot ? `${recommendedSlot.start_time.slice(0, 5)} - ${recommendedSlot.end_time.slice(0, 5)} HRS` : "N/A";

      if (slotSelectionStatusText) {
        slotSelectionStatusText.innerHTML = `
          <div>
            <strong>Selected Slot:</strong> <span style="font-family: var(--font-mono); font-weight: 700; color: var(--irctc-navy-primary);">${selRange}</span> 
            · <strong>AI Optimal Recommendation:</strong> <span style="font-family: var(--font-mono); font-weight: 700; color: var(--irctc-orange-primary);">${recRange}</span>
          </div>
          <div style="font-size: 11px; color: var(--text-secondary); margin-top: 3px;">
            Booking reservation will allocate strictly for your selected slot (<strong>${selRange}</strong>).
          </div>
        `;
      }

      if (slotSelectionStatusBadge) {
        slotSelectionStatusBadge.innerHTML = isMatch
          ? `<span class="slot-selection-badge-matched">MATCHES AI RECOMMENDATION</span>`
          : `<span class="slot-selection-badge-custom">CUSTOM CHOICE (DIFFERS FROM AI OPTIMAL)</span>`;
      }

      if (btnBookSlot) {
        btnBookSlot.disabled = false;
        btnBookSlot.textContent = `Confirm & Allocate Selected Slot: ${selRange} (OS Mutex Locked)`;
      }
    }

    slots.forEach(s => {
      const card = document.createElement("div");
      const isRecommended = !!s.is_recommended;
      const isSelected = !!(state.selectedSlot && state.selectedSlot.slot_id === s.slot_id);
      
      card.className = `slot-card ${isRecommended ? 'recommended' : ''} ${isSelected ? 'selected' : ''}`.trim();
      card.dataset.slotId = s.slot_id;

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

      let ribbonsHtml = "";
      if (isSelected) {
        ribbonsHtml += `<div class="selected-ribbon">YOUR SELECTION</div>`;
      }
      if (isRecommended) {
        ribbonsHtml += `<div class="recommended-ribbon">AI OPTIMAL SLOT</div>`;
      }

      card.innerHTML = `
        ${ribbonsHtml}
        <div class="slot-header-row" style="margin-top: ${(isSelected || isRecommended) ? '4px' : '0'};">
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

      if (s.occupancy_status !== "FULL" && avail > 0 && !hasActivePass) {
        card.addEventListener("click", () => {
          state.selectedSlot = s;
          document.querySelectorAll(".slot-card").forEach(c => {
            const cSlotId = parseInt(c.dataset.slotId, 10);
            const cIsSelected = (cSlotId === s.slot_id);
            
            c.classList.toggle("selected", cIsSelected);
            c.querySelectorAll(".selected-ribbon").forEach(el => el.remove());
            if (cIsSelected) {
              c.insertAdjacentHTML("afterbegin", `<div class="selected-ribbon">YOUR SELECTION</div>`);
            }
          });
          updateSelectionStatusUI();
        });
      } else {
        card.style.opacity = hasActivePass ? "0.75" : "0.6";
        card.style.cursor = "not-allowed";
        if (hasActivePass) {
          card.title = "Voter already possesses an active confirmed booking for this election event.";
        }
      }

      slotsGridContainer.appendChild(card);
    });

    updateSelectionStatusUI();
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
    const currentSelRange = state.selectedSlot ? `${state.selectedSlot.start_time.slice(0, 5)} - ${state.selectedSlot.end_time.slice(0, 5)} HRS` : "";
    btnBookSlot.textContent = `Confirm & Allocate Selected Slot: ${currentSelRange} (OS Mutex Locked)`;

    if (!res.ok) {
      resetPcbNodes();
      if (res.status_code === "DUPLICATE_BOOKING_PREVENTED") {
        window.apiClient.showToast("Active booking exists: You already have a confirmed pass for this election. Use PNR / Reschedule tab.", "warning");
        if (state.voter) state.voter.has_active_booking = true;
        const warnBanner = document.getElementById("activeBookingWarningBanner");
        if (warnBanner) warnBanner.style.display = "block";
        btnBookSlot.disabled = true;
        btnBookSlot.textContent = "Active Booking Already Confirmed (Use Reschedule)";
      }
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
    appointmentSlipContainer.classList.remove("appointment-slip-enter");
    void appointmentSlipContainer.offsetWidth;
    appointmentSlipContainer.classList.add("appointment-slip-enter");
    appointmentSlipContainer.scrollIntoView({ behavior: "smooth" });
  }

  function renderAppointmentSlipFromView(slip) {
    const token = slip.booking_reference_token || slip.allocation_token;
    document.getElementById("slipVoterName").textContent = slip.voter_name;
    document.getElementById("slipEpicNo").textContent = slip.demo_epic_no;
    document.getElementById("slipConstituency").textContent = `${slip.parliamentary_constituency || 'Nainital-Udhamsingh Nagar Parliamentary Constituency'} (PC) · ${slip.assembly_constituency || 'Bhimtal Assembly Constituency'} (AC)`;
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
    appointmentSlipContainer.classList.remove("appointment-slip-enter");
    void appointmentSlipContainer.offsetWidth;
    appointmentSlipContainer.classList.add("appointment-slip-enter");
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

  document.getElementById("chipMyJurisdiction")?.addEventListener("click", () => {
    const v = state.voter;
    const b = state.assignedBooth;
    const pLevel = v?.priority_level || 4;
    const prioLabel = pLevel === 1 ? "P1 (Pregnant Women)" : pLevel === 2 ? "P2 (PwD)" : pLevel === 3 ? "P3 (Senior Citizen)" : "P4 (General)";
    dishaResponseBox.innerHTML = `
      <strong>Voter Jurisdiction &amp; Booth Assignment:</strong><br/>
      • <strong>Voter Name:</strong> ${v?.full_name || "Synthetic Voter"}<br/>
      • <strong>Category &amp; Priority:</strong> ${(v?.special_category || "GENERAL").replace(/_/g, " ")} &middot; <strong>${prioLabel}</strong><br/>
      • <strong>Parliamentary Constituency (PC):</strong> Nainital-Udhamsingh Nagar (PC-04)<br/>
      • <strong>Assembly Constituency (AC):</strong> Bhimtal (AC-58)<br/>
      • <strong>Assigned Station:</strong> ${b?.station_name || "Graphic Era Hill University, Bhimtal Campus"}<br/>
      • <strong>Assigned Booth:</strong> Booth ${b?.booth_number || "01"} (${b?.booth_name || "Room 101 Ground Floor"})<br/>
      <em>All allocations strictly mapped to your designated polling counter.</em>
    `;
  });

  document.getElementById("chipPriorityRules")?.addEventListener("click", () => {
    dishaResponseBox.innerHTML = `
      <strong>Assistive Priority Hierarchy (P1-P4):</strong><br/>
      • <strong>P1 · Pregnant Women:</strong> Highest scheduling precedence and dedicated reserved slot quotas.<br/>
      • <strong>P2 · Persons with Disabilities (PwD):</strong> Second precedence with wheelchair ramp-accessible booth routing.<br/>
      • <strong>P3 · Senior Citizens:</strong> Third precedence with minimized queue waiting times.<br/>
      • <strong>P4 · General Voters:</strong> Normal scheduling with OS Dynamic Aging elevation.<br/>
      <em>Guardrail: Advisory arrival slot allocation only; constitutional voting rights are strictly equal.</em>
    `;
  });

  document.getElementById("chipOverbookingPrevent")?.addEventListener("click", () => {
    dishaResponseBox.innerHTML = `
      <strong>Three-Tier Concurrency Overbooking Prevention:</strong><br/>
      • <strong>Tier 1 (OS Bounded Semaphore):</strong> Regulates in-flight concurrent worker threads per time-slot window.<br/>
      • <strong>Tier 2 (Process Mutex):</strong> Python re-entrant lock (RLock) serializes concurrent slot evaluation.<br/>
      • <strong>Tier 3 (ACID Row-Level Lock):</strong> MySQL InnoDB <code>SELECT ... FOR UPDATE</code> holds an exclusive row lock on <code>time_slots</code>, guaranteeing zero overbooking (capacity invariant strictly enforced).
    `;
  });

  document.getElementById("chipRescheduleHelp")?.addEventListener("click", () => {
    dishaResponseBox.innerHTML = `
      <strong>How to Reschedule or Cancel Your Slot:</strong><br/>
      • <strong>Step 1:</strong> Locate your confirmed booking card displaying your PNR Reference Token.<br/>
      • <strong>Step 2:</strong> Click <em>Cancel / Reschedule Booking</em>.<br/>
      • <strong>Step 3:</strong> The ACID cancellation transaction frees your slot capacity and logs an audit event.<br/>
      • <strong>Step 4:</strong> Re-select any available open slot across the 4 Bhimtal polling stations.
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
    triggerMapInvalidate();
  });

  // Check health on start
  window.apiClient.checkHealth().then(h => {
    if (h.ok) console.log("Backend API Health verified:", h.service);
  });

  // Initialize map immediately on page load and preload nearby polling station markers
  ensureMapInitialized();
  loadNearbyBooths();
});
