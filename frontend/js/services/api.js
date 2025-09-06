/**
 * API Service - Handles all backend communication
 */

export class API {
  constructor(baseURL = "") {
    this.baseURL = baseURL || window.location.origin;
    this.apiPrefix = "/api";
    this.timeout = 30000; // 30 seconds
    this.cache = new Map();
    this.cacheTimeout = 60000; // 1 minute cache
  }

  /**
   * Make an API request
   * @private
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${this.apiPrefix}${endpoint}`;

    const defaultOptions = {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      mode: "cors",
      credentials: "same-origin",
    };

    const config = { ...defaultOptions, ...options };

    // Add body if provided
    if (options.body && typeof options.body === "object") {
      config.body = JSON.stringify(options.body);
    }

    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    config.signal = controller.signal;

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(
          error.message || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        throw new Error("Request timeout");
      }

      throw error;
    }
  }

  /**
   * GET request with caching
   * @private
   */
  async get(endpoint, options = {}) {
    const cacheKey = endpoint + JSON.stringify(options);

    // Check cache
    if (this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey);
      if (Date.now() - cached.timestamp < this.cacheTimeout) {
        return cached.data;
      }
    }

    // Make request
    const data = await this.request(endpoint, { ...options, method: "GET" });

    // Cache result
    this.cache.set(cacheKey, {
      data,
      timestamp: Date.now(),
    });

    return data;
  }

  /**
   * Clear cache
   */
  clearCache() {
    this.cache.clear();
  }

  // ============ Models API ============

  async getModels(filters = {}) {
    const params = new URLSearchParams();

    if (filters.search) params.append("search", filters.search);
    if (filters.type) params.append("type", filters.type);
    if (filters.hasNotes !== undefined)
      params.append("has_notes", filters.hasNotes);
    if (filters.sort) params.append("sort", filters.sort);
    if (filters.order) params.append("order", filters.order);

    const query = params.toString();
    const endpoint = query ? `/models?${query}` : "/models";

    return await this.get(endpoint);
  }

  async getModel(modelId) {
    return await this.get(`/models/${modelId}`);
  }

  async deleteModel(modelId) {
    return await this.request(`/models/${modelId}`, { method: "DELETE" });
  }

  async getModelTags(modelId) {
    return await this.get(`/models/${modelId}/tags`);
  }

  async addModelTag(modelId, tag) {
    return await this.request(`/models/${modelId}/tags`, {
      method: "POST",
      body: { tag },
    });
  }

  async generateModelHash(modelId) {
    return await this.request(`/models/${modelId}/hash`, { method: "POST" });
  }

  async getStatistics() {
    return await this.get("/models/statistics");
  }

  async getModelTypes() {
    return await this.get("/models/types");
  }

  // ============ Notes API ============

  async getNotes(modelId) {
    return await this.get(`/notes/${modelId}`);
  }

  async saveNotes(modelId, content, createBackup = true) {
    return await this.request(`/notes/${modelId}`, {
      method: "POST",
      body: { content, create_backup: createBackup },
    });
  }

  async getNotesTemplate(modelId, templateType) {
    return await this.get(`/notes/${modelId}/template/${templateType}`);
  }

  async getNotesBackups(modelId) {
    return await this.get(`/notes/${modelId}/backups`);
  }

  async restoreNotesBackup(modelId, backupId = null, backupFilename = null) {
    return await this.request(`/notes/${modelId}/restore`, {
      method: "POST",
      body: { backup_id: backupId, backup_filename: backupFilename },
    });
  }

  async getNotesTemplates() {
    return await this.get("/notes/templates");
  }

  async exportNotes() {
    return await this.get("/notes/export");
  }

  // ============ Settings API ============

  async getSettings() {
    const result = await this.get("/settings");
    return result.settings || result;
  }

  async updateSettings(settings) {
    return await this.request("/settings", {
      method: "POST",
      body: settings,
    });
  }

  async resetSettings() {
    return await this.request("/settings/reset", { method: "POST" });
  }

  async getSystemInfo() {
    return await this.get("/settings/system");
  }

  async exportSettings() {
    return await this.get("/settings/export");
  }

  async importSettings(data) {
    return await this.request("/settings/import", {
      method: "POST",
      body: data,
    });
  }

  // ============ Scan API ============

  async startScan(directory = null, recursive = true) {
    return await this.request("/scan", {
      method: "POST",
      body: { directory, recursive },
    });
  }

  async getScanStatus() {
    return await this.get("/scan/status");
  }

  async validateDirectory(directory) {
    return await this.request("/scan/validate", {
      method: "POST",
      body: { directory },
    });
  }

  async getScanHistory(limit = 10) {
    return await this.get(`/scan/history?limit=${limit}`);
  }

  async refreshModels() {
    return await this.request("/scan/refresh", { method: "POST" });
  }

  // ============ ComfyUI API ============

  async checkComfyUIConnection() {
    try {
      const response = await fetch("http://localhost:8188/system_stats", {
        method: "GET",
        mode: "cors",
        signal: AbortSignal.timeout(5000),
      });

      return response.ok;
    } catch {
      return false;
    }
  }

  async getComfyUIStatus() {
    try {
      const response = await fetch("http://localhost:8188/queue", {
        method: "GET",
        mode: "cors",
        signal: AbortSignal.timeout(5000),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      return null;
    }
  }

  // ============ Utility Methods ============

  /**
   * Upload a file
   */
  async uploadFile(file, endpoint) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(
      `${this.baseURL}${this.apiPrefix}${endpoint}`,
      {
        method: "POST",
        body: formData,
        credentials: "same-origin",
      }
    );

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Download a file
   */
  async downloadFile(endpoint, filename) {
    const response = await fetch(
      `${this.baseURL}${this.apiPrefix}${endpoint}`,
      {
        method: "GET",
        credentials: "same-origin",
      }
    );

    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.style.display = "none";
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  /**
   * Batch requests
   */
  async batch(requests) {
    return await Promise.all(
      requests.map((req) =>
        this.request(req.endpoint, req.options).catch((err) => ({
          error: err.message,
          endpoint: req.endpoint,
        }))
      )
    );
  }
}
