/**
 * API Client Module
 * Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
 * Module: frontend/js/api_client.js
 * 
 * Provides unified, robust Fetch wrapper for all 12 REST API endpoints + race simulation,
 * token handling, telemetry header capture, and non-intrusive toast alerts.
 */

class ApiClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
    this.adminTokenKey = "onoe_admin_jwt";
    this.voterTokenKey = "onoe_voter_jwt";
    this.lastEngineHeader = null;
  }

  // ---------------------------------------------------------------------------
  // Token Storage Helpers
  // ---------------------------------------------------------------------------
  getAdminToken() {
    return localStorage.getItem(this.adminTokenKey) || sessionStorage.getItem(this.adminTokenKey);
  }

  setAdminToken(token, remember = true) {
    if (remember) {
      localStorage.setItem(this.adminTokenKey, token);
    } else {
      sessionStorage.setItem(this.adminTokenKey, token);
    }
  }

  clearAdminToken() {
    localStorage.removeItem(this.adminTokenKey);
    sessionStorage.removeItem(this.adminTokenKey);
  }

  getVoterToken() {
    return localStorage.getItem(this.voterTokenKey) || sessionStorage.getItem(this.voterTokenKey);
  }

  setVoterToken(token) {
    sessionStorage.setItem(this.voterTokenKey, token);
  }

  clearVoterToken() {
    localStorage.removeItem(this.voterTokenKey);
    sessionStorage.removeItem(this.voterTokenKey);
  }

  // ---------------------------------------------------------------------------
  // Core Request Wrapper
  // ---------------------------------------------------------------------------
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {})
    };

    // Auto-attach authorization if not explicitly provided
    if (!headers["Authorization"]) {
      const adminToken = this.getAdminToken();
      const voterToken = this.getVoterToken();
      if (adminToken && endpoint.includes("/admin")) {
        headers["Authorization"] = `Bearer ${adminToken}`;
      } else if (voterToken) {
        headers["Authorization"] = `Bearer ${voterToken}`;
      } else if (adminToken) {
        headers["Authorization"] = `Bearer ${adminToken}`;
      }
    }

    try {
      const response = await fetch(url, { ...options, headers });
      
      // Capture OS telemetry headers
      this.lastEngineHeader = response.headers.get("X-OS-Concurrency-Engine");

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.message || `HTTP error ${response.status}: ${response.statusText}`;
        const errorCode = data.error || data.status_code || response.status;
        
        // Non-intrusive toast notification based on status
        if (response.status === 409) {
          this.showToast(`Conflict: ${errorMsg}`, "warning");
        } else if (response.status === 401) {
          this.showToast(`Unauthorized: ${errorMsg}`, "error");
        } else if (response.status === 403) {
          this.showToast(`Access Forbidden: ${errorMsg}`, "error");
        } else if (response.status === 404) {
          this.showToast(`Not Found: ${errorMsg}`, "warning");
        } else if (response.status >= 400 && response.status < 500) {
          this.showToast(`Validation: ${errorMsg}`, "warning");
        } else if (response.status >= 500) {
          this.showToast(`Server Error: ${errorMsg}`, "error");
        }

        return {
          ok: false,
          status: response.status,
          status_code: response.status,
          error: errorCode,
          message: errorMsg,
          data
        };
      }

      return {
        ok: true,
        status: response.status,
        ...data
      };
    } catch (err) {
      this.showToast(`Network Error: Could not connect to API server.`, "error");
      return {
        ok: false,
        status: 0,
        error: "NETWORK_ERROR",
        message: err.message
      };
    }
  }

  // ---------------------------------------------------------------------------
  // 12 REST API Methods + Race Simulator
  // ---------------------------------------------------------------------------

  // 1. POST /api/auth/login (Admin Login)
  async loginAdmin(username, password) {
    const res = await this.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
    if (res.ok && res.access_token) {
      this.setAdminToken(res.access_token);
      this.showToast(`Welcome back, ${res.user?.name || username}!`, "success");
    }
    return res;
  }

  // 1b. POST /api/auth/login (Voter Session Login)
  async loginVoter(demo_epic_no, voter_id = null) {
    const res = await this.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ demo_epic_no, voter_id })
    });
    if (res.ok && res.access_token) {
      this.setVoterToken(res.access_token);
      this.showToast(`Voter verified: ${res.user?.name || demo_epic_no}`, "success");
    }
    return res;
  }

  // 2. POST /api/voters/register
  async registerVoter(voterData) {
    return await this.request("/api/voters/register", {
      method: "POST",
      body: JSON.stringify(voterData)
    });
  }

  async lookupVoter(demo_epic_no) {
    return await this.request("/api/voters/register", {
      method: "POST",
      body: JSON.stringify({ demo_epic_no, action: "lookup" })
    });
  }

  // 3. POST /api/verification/mock
  async verifyMock(voterId, boothId, consentGiven = true, method = "SIMULATED_OTP", mockInput = null) {
    return await this.request("/api/verification/mock", {
      method: "POST",
      body: JSON.stringify({
        voter_id: parseInt(voterId, 10),
        booth_id: parseInt(boothId, 10),
        consent_given: consentGiven,
        verification_method: method,
        mock_input: mockInput
      })
    });
  }

  // 4. GET /api/booths/nearby
  async getNearbyBooths(lat = 30.34215, lon = 78.02148, constituencyId = null, accessibilityNeeded = false) {
    const params = new URLSearchParams({ lat, lon });
    if (constituencyId) params.append("constituency_id", constituencyId);
    if (accessibilityNeeded) params.append("accessibility_needed", "true");

    return await this.request(`/api/booths/nearby?${params.toString()}`, {
      method: "GET"
    });
  }

  // 5. GET /api/slots/available
  async getAvailableSlots(boothId, voterId = null, eventId = 1) {
    const params = new URLSearchParams({ booth_id: boothId, event_id: eventId });
    if (voterId) params.append("voter_id", voterId);

    return await this.request(`/api/slots/available?${params.toString()}`, {
      method: "GET"
    });
  }

  // 6. POST /api/allocations
  async createAllocation(voterId, boothId, slotId, allocationType = "USER_RESERVED") {
    return await this.request("/api/allocations", {
      method: "POST",
      body: JSON.stringify({
        voter_id: parseInt(voterId, 10),
        booth_id: parseInt(boothId, 10),
        slot_id: parseInt(slotId, 10),
        allocation_type: allocationType
      })
    });
  }

  // 7. GET /api/allocations/<id>
  async getAllocationSlip(allocIdOrToken) {
    return await this.request(`/api/allocations/${encodeURIComponent(allocIdOrToken)}`, {
      method: "GET"
    });
  }

  // 8. DELETE /api/allocations/<id>
  async cancelAllocation(allocIdOrToken) {
    return await this.request(`/api/allocations/${encodeURIComponent(allocIdOrToken)}`, {
      method: "DELETE"
    });
  }

  // 9. GET /api/admin/dashboard
  async getAdminDashboard() {
    return await this.request("/api/admin/dashboard", {
      method: "GET"
    });
  }

  // 10. POST /api/admin/booths
  async createOrUpdateBooth(boothData) {
    return await this.request("/api/admin/booths", {
      method: "POST",
      body: JSON.stringify(boothData)
    });
  }

  // 11. POST /api/admin/slots
  async createOrUpdateSlot(slotData) {
    return await this.request("/api/admin/slots", {
      method: "POST",
      body: JSON.stringify(slotData)
    });
  }

  // 12. GET /api/admin/crowd-predictions
  async getAdminCrowdPredictions() {
    return await this.request("/api/admin/crowd-predictions", {
      method: "GET"
    });
  }

  // 13. POST /api/admin/simulate-race (Live Viva 10-Thread Demo)
  async simulateRaceCondition() {
    return await this.request("/api/admin/simulate-race", {
      method: "POST",
      body: JSON.stringify({ demo: true })
    });
  }

  // Health check
  async checkHealth() {
    return await this.request("/api/health", {
      method: "GET"
    });
  }

  // ---------------------------------------------------------------------------
  // Toast Notification UI Helper
  // ---------------------------------------------------------------------------
  showToast(message, type = "info") {
    let container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let iconSvg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    if (type === "success") {
      iconSvg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === "error") {
      iconSvg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else if (type === "warning") {
      iconSvg = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    }

    toast.innerHTML = `<span class="toast-icon">${iconSvg}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }
}

// Global Singleton Instance
window.apiClient = new ApiClient();
