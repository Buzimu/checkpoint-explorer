/**
 * SettingsModal Component - Settings configuration dialog
 */
export class SettingsModal {
  constructor(container, store, api) {
    this.container = container || this.createContainer();
    this.store = store;
    this.api = api;
    this.isOpen = false;

    this.render();
  }

  createContainer() {
    const modal = document.createElement("div");
    modal.id = "settings-modal";
    modal.className = "modal-overlay";
    modal.style.display = "none";
    document.body.appendChild(modal);
    return modal;
  }

  render() {
    const settings = this.store.getState("settings");

    this.container.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <h3>⚙️ Settings</h3>
          <button class="modal-close">×</button>
        </div>
        
        <div class="modal-body">
          <div class="setting-group">
            <label class="setting-label">Models Directory</label>
            <div class="directory-input-group">
              <input type="text" 
                     class="setting-input" 
                     id="models-directory"
                     value="${settings.models_directory || ""}"
                     placeholder="e.g., C:\\ComfyUI\\models or /home/user/ComfyUI/models">
              <button class="btn btn-secondary" id="browse-btn">📂 Browse</button>
            </div>
            <small class="setting-help">
              Enter the full path to your ComfyUI models directory 
              (should contain subfolders like 'checkpoints', 'loras', 'vae', etc.)
            </small>
          </div>
          
          <div class="setting-group">
            <label class="setting-checkbox">
              <input type="checkbox" 
                     id="auto-scan" 
                     ${settings.auto_scan ? "checked" : ""}>
              <span>Auto-scan on startup</span>
            </label>
            <small class="setting-help">
              Automatically scan for new models when the app starts
            </small>
          </div>
          
          <div class="setting-group">
            <label class="setting-checkbox">
              <input type="checkbox" 
                     id="scan-recursive" 
                     ${settings.scan_recursive !== false ? "checked" : ""}>
              <span>Scan subdirectories</span>
            </label>
            <small class="setting-help">
              Recursively scan all subdirectories for models
            </small>
          </div>
          
          <div class="setting-group">
            <label class="setting-checkbox">
              <input type="checkbox" 
                     id="show-examples" 
                     ${settings.show_examples ? "checked" : ""}>
              <span>Show example images</span>
            </label>
            <small class="setting-help">
              Display example images in model details (when available)
            </small>
          </div>
          
          <div class="setting-group">
            <label class="setting-label">Theme</label>
            <select class="setting-input" id="theme-select">
              <option value="dark" ${
                settings.theme === "dark" ? "selected" : ""
              }>Dark</option>
              <option value="light" ${
                settings.theme === "light" ? "selected" : ""
              }>Light</option>
            </select>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" id="cancel-btn">Cancel</button>
          <button class="btn btn-primary" id="save-btn">
            <span class="save-btn-text">Save & Scan Models</span>
          </button>
        </div>
        
        <div class="scan-progress" style="display: none;">
          <div class="progress-bar">
            <div class="progress-fill"></div>
          </div>
          <div class="progress-text">
            <span class="progress-message">Initializing scan...</span>
            <span class="progress-percent">0%</span>
          </div>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    // Close button
    const closeBtn = this.container.querySelector(".modal-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => this.close());
    }

    // Cancel button
    const cancelBtn = this.container.querySelector("#cancel-btn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => this.close());
    }

    // Save button
    const saveBtn = this.container.querySelector("#save-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => this.save());
    }

    // Browse button
    const browseBtn = this.container.querySelector("#browse-btn");
    if (browseBtn) {
      browseBtn.addEventListener("click", () => this.browseDirectory());
    }

    // Click outside to close
    this.container.addEventListener("click", (e) => {
      if (e.target === this.container) {
        this.close();
      }
    });

    // Enter key in directory input
    const directoryInput = this.container.querySelector("#models-directory");
    if (directoryInput) {
      directoryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.save();
        }
      });
    }
  }

  open() {
    this.isOpen = true;
    this.container.style.display = "flex";
    this.store.setState({
      ui: { ...this.store.getState("ui"), settingsOpen: true },
    });

    // Focus the directory input
    setTimeout(() => {
      const input = this.container.querySelector("#models-directory");
      if (input) input.focus();
    }, 100);
  }

  close() {
    this.isOpen = false;
    this.container.style.display = "none";
    this.store.setState({
      ui: { ...this.store.getState("ui"), settingsOpen: false },
    });
  }

  async save() {
    const directory = this.container.querySelector("#models-directory").value;
    const autoScan = this.container.querySelector("#auto-scan").checked;
    const scanRecursive =
      this.container.querySelector("#scan-recursive").checked;
    const showExamples = this.container.querySelector("#show-examples").checked;
    const theme = this.container.querySelector("#theme-select").value;

    if (!directory || !directory.trim()) {
      alert("Please enter a models directory path");
      return;
    }

    // Disable save button
    const saveBtn = this.container.querySelector("#save-btn");
    const saveBtnText = this.container.querySelector(".save-btn-text");
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtnText.textContent = "Saving...";
    }

    try {
      // First validate the directory
      const validation = await this.api.validateDirectory(directory);

      if (!validation.valid) {
        alert(`Invalid directory: ${validation.message}`);
        return;
      }

      if (validation.warning) {
        const proceed = confirm(`${validation.message}\n\nContinue anyway?`);
        if (!proceed) return;
      }

      // Save settings
      const settings = {
        models_directory: directory,
        auto_scan: autoScan,
        scan_recursive: scanRecursive,
        show_examples: showExamples,
        theme: theme,
      };

      await this.api.updateSettings(settings);

      // Update store
      this.store.setState({ settings });

      // Apply theme
      document.body.className = theme === "light" ? "light-theme" : "";

      // Show scan progress
      this.showScanProgress();

      // Start scan
      await this.api.startScan(directory, scanRecursive);

      // Poll for scan status
      this.pollScanStatus();
    } catch (error) {
      console.error("Failed to save settings:", error);
      alert("Failed to save settings: " + error.message);
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtnText.textContent = "Save & Scan Models";
      }
    }
  }

  showScanProgress() {
    const progressSection = this.container.querySelector(".scan-progress");
    if (progressSection) {
      progressSection.style.display = "block";
    }
  }

  hideScanProgress() {
    const progressSection = this.container.querySelector(".scan-progress");
    if (progressSection) {
      progressSection.style.display = "none";
    }
  }

  updateScanProgress(progress) {
    const progressFill = this.container.querySelector(".progress-fill");
    const progressMessage = this.container.querySelector(".progress-message");
    const progressPercent = this.container.querySelector(".progress-percent");

    if (progressFill) {
      progressFill.style.width = `${progress.progress}%`;
    }

    if (progressMessage) {
      progressMessage.textContent = progress.message || "Scanning...";
    }

    if (progressPercent) {
      const percent =
        Math.round((progress.progress / progress.total) * 100) || 0;
      progressPercent.textContent = `${percent}%`;
    }
  }

  async pollScanStatus() {
    const pollInterval = setInterval(async () => {
      try {
        const status = await this.api.getScanStatus();

        if (status.scan) {
          this.updateScanProgress(status.scan);

          if (!status.scan.active) {
            clearInterval(pollInterval);

            // Hide progress after a delay
            setTimeout(() => {
              this.hideScanProgress();
              this.close();
            }, 2000);

            // Reload models
            const modelsData = await this.api.getModels();
            this.store.setState({
              models: modelsData.models || [],
              totalModels: modelsData.total || 0,
            });

            // Show notification
            document.dispatchEvent(
              new CustomEvent("notification:show", {
                detail: {
                  message: `Scan complete! Found ${modelsData.total} models`,
                  type: "success",
                },
              })
            );
          }
        }
      } catch (error) {
        clearInterval(pollInterval);
        this.hideScanProgress();
        console.error("Failed to get scan status:", error);
      }
    }, 1000);
  }

  browseDirectory() {
    // In a web app, we can't actually browse directories
    // Show helpful message instead
    const isWindows = navigator.platform.includes("Win");
    const examples = isWindows
      ? [
          "Windows Examples:",
          "C:\\ComfyUI\\models",
          "D:\\AI\\ComfyUI\\models",
          "S:\\AI\\Image Models\\models",
          "",
          "Your path should contain subdirectories like:",
          "- checkpoints/",
          "- loras/",
          "- vae/",
          "- controlnet/",
        ]
      : [
          "Mac/Linux Examples:",
          "/Users/username/ComfyUI/models",
          "/home/username/comfyui/models",
          "~/ComfyUI/models",
          "",
          "Your path should contain subdirectories like:",
          "- checkpoints/",
          "- loras/",
          "- vae/",
          "- controlnet/",
        ];

    alert(examples.join("\n"));

    // Focus the input
    const input = this.container.querySelector("#models-directory");
    if (input) {
      input.focus();
      input.select();
    }
  }
}
