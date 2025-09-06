// Main Alpine.js data and functionality - FIXED VERSION
function modelExplorer() {
  return {
    // Data - make sure ALL properties are defined
    models: [],
    filteredModels: [],
    selectedModel: null,
    searchQuery: "",
    selectedType: "all",
    isConnected: false,
    loading: false,
    showSettings: false,

    // Notes Editor
    notesEditor: {
      isOpen: false,
      content: "",
      originalContent: "",
      isDirty: false,
      autoSaveStatus: "saved", // 'saved', 'saving', 'dirty'
      lastSaved: null,
      charCount: 0,
      wordCount: 0,
      showTemplateDropdown: false,
      backups: [],
      templates: [
        {
          id: "checkpoint",
          name: "Checkpoint Model",
          description: "Standard template for checkpoint models",
        },
        {
          id: "lora",
          name: "LoRA Model",
          description: "Template for LoRA fine-tuning models",
        },
        {
          id: "vae",
          name: "VAE Model",
          description: "Template for VAE models",
        },
        {
          id: "controlnet",
          name: "ControlNet",
          description: "Template for ControlNet models",
        },
        {
          id: "embedding",
          name: "Embedding",
          description: "Template for textual inversions",
        },
      ],
    },

    // Add these methods to your modelExplorer() function:

    closeNotesEditor() {
      if (this.notesEditor.isDirty) {
        const shouldClose = confirm(
          "You have unsaved changes. Are you sure you want to close?"
        );
        if (!shouldClose) return;
      }

      this.notesEditor.isOpen = false;
      this.notesEditor.content = "";
      this.notesEditor.originalContent = "";
      this.notesEditor.isDirty = false;
      this.notesEditor.showTemplateDropdown = false;
      console.log("📝 Notes editor closed");
    },

    async saveAndCloseNotes() {
      const saveResult = await this.saveNotes();
      if (saveResult) {
        this.closeNotesEditor();
      }
    },

    async saveNotes() {
      if (!this.selectedModel) {
        this.showNotification("No model selected", "error");
        return false;
      }

      try {
        this.notesEditor.autoSaveStatus = "saving";

        const response = await fetch(`/api/notes/${this.selectedModel.id}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            content: this.notesEditor.content,
            create_backup: true,
          }),
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const result = await response.json();

        if (result.status === "success") {
          this.notesEditor.originalContent = this.notesEditor.content;
          this.notesEditor.isDirty = false;
          this.notesEditor.autoSaveStatus = "saved";
          this.notesEditor.lastSaved = new Date();

          // Update the model in the list
          this.selectedModel.notes = this.notesEditor.content;
          this.selectedModel.has_notes = Boolean(
            this.notesEditor.content.trim()
          );

          this.showNotification("Notes saved successfully!", "success");
          return true;
        } else {
          throw new Error(result.message || "Failed to save notes");
        }
      } catch (error) {
        console.error("❌ Failed to save notes:", error);
        this.notesEditor.autoSaveStatus = "dirty";
        this.showNotification(
          "Failed to save notes: " + error.message,
          "error"
        );
        return false;
      }
    },

    onNotesInput() {
      const currentContent = this.notesEditor.content || "";
      this.notesEditor.isDirty =
        currentContent !== this.notesEditor.originalContent;
      this.notesEditor.autoSaveStatus = this.notesEditor.isDirty
        ? "dirty"
        : "saved";
      this.updateNotesStats();
    },

    updateNotesStats() {
      const content = this.notesEditor.content || "";
      this.notesEditor.charCount = content.length;
      this.notesEditor.wordCount = content.trim()
        ? content.trim().split(/\s+/).length
        : 0;
    },

    getAutoSaveStatusText() {
      switch (this.notesEditor.autoSaveStatus) {
        case "saving":
          return "Saving...";
        case "dirty":
          return "Unsaved changes";
        case "saved":
          return "All changes saved";
        default:
          return "Ready";
      }
    },

    getAutoSaveStatusColor() {
      switch (this.notesEditor.autoSaveStatus) {
        case "saving":
          return "#ffb86c";
        case "dirty":
          return "#ff5555";
        case "saved":
          return "#50fa7b";
        default:
          return "#6272a4";
      }
    },

    handleNotesKeydown(event) {
      // Save with Ctrl+S
      if (event.ctrlKey && event.key === "s") {
        event.preventDefault();
        this.saveNotes();
      }

      // Close with Escape (if no unsaved changes)
      if (event.key === "Escape" && !this.notesEditor.isDirty) {
        this.closeNotesEditor();
      }
    },

    // Template functions
    toggleTemplateDropdown() {
      this.notesEditor.showTemplateDropdown =
        !this.notesEditor.showTemplateDropdown;
    },

    async applyTemplate(templateId) {
      if (!this.selectedModel) return;

      try {
        const response = await fetch(
          `/api/notes/${this.selectedModel.id}/template/${templateId}`
        );
        if (response.ok) {
          const result = await response.json();
          this.notesEditor.content = result.content;
          this.onNotesInput();
          this.notesEditor.showTemplateDropdown = false;
          this.showNotification(`Applied ${templateId} template`, "success");
        }
      } catch (error) {
        console.error("Failed to apply template:", error);
        this.showNotification("Failed to apply template", "error");
      }
    },

    // Formatting functions
    insertFormatting(before, after) {
      const textarea = document.getElementById("notesTextarea");
      if (!textarea) return;

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const selectedText = textarea.value.substring(start, end);

      const replacement = before + selectedText + after;
      const newContent =
        textarea.value.substring(0, start) +
        replacement +
        textarea.value.substring(end);

      this.notesEditor.content = newContent;
      this.onNotesInput();

      // Restore cursor position
      setTimeout(() => {
        const newCursorPos = selectedText
          ? start + before.length + selectedText.length + after.length
          : start + before.length;
        textarea.setSelectionRange(newCursorPos, newCursorPos);
        textarea.focus();
      }, 0);
    },

    insertText(text) {
      const textarea = document.getElementById("notesTextarea");
      if (!textarea) return;

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;

      const newContent =
        textarea.value.substring(0, start) +
        text +
        textarea.value.substring(end);
      this.notesEditor.content = newContent;
      this.onNotesInput();

      // Set cursor position after inserted text
      setTimeout(() => {
        const newCursorPos = start + text.length;
        textarea.setSelectionRange(newCursorPos, newCursorPos);
        textarea.focus();
      }, 0);
    },

    async restoreBackup(backupFilename) {
      if (!this.selectedModel) return;

      try {
        const response = await fetch(
          `/api/notes/${this.selectedModel.id}/restore`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              backup_filename: backupFilename,
            }),
          }
        );

        if (response.ok) {
          const result = await response.json();
          // Reload the notes content
          const notesResponse = await fetch(
            `/api/notes/${this.selectedModel.id}`
          );
          if (notesResponse.ok) {
            const notesData = await notesResponse.json();
            this.notesEditor.content = notesData.content || "";
            this.notesEditor.originalContent = this.notesEditor.content;
            this.notesEditor.isDirty = false;
            this.updateNotesStats();
            this.showNotification("Backup restored successfully!", "success");
          }
        } else {
          throw new Error("Failed to restore backup");
        }
      } catch (error) {
        console.error("Failed to restore backup:", error);
        this.showNotification(
          "Failed to restore backup: " + error.message,
          "error"
        );
      }
    },

    // Settings form
    settingsForm: {
      models_directory: "",
      auto_scan: true,
      show_examples: true,
    },

    // Scan progress
    scanProgress: {
      active: false,
      percent: 0,
      current: 0,
      total: 0,
      message: "Initializing scan...",
    },

    // Initialize
    async init() {
      console.log("🎨 ComfyUI Model Explorer initializing...");
      console.log(
        "⚙️ Alpine.js version:",
        window.Alpine ? "loaded" : "not loaded"
      );

      try {
        await this.loadSettings();
        await this.loadModels();
        this.checkComfyUIConnection();

        // Set up periodic connection check
        setInterval(() => {
          this.checkComfyUIConnection();
        }, 30000);

        console.log("✅ Initialization complete");
      } catch (error) {
        console.error("❌ Initialization failed:", error);
      }
    },

    // Load settings from server
    async loadSettings() {
      try {
        const response = await fetch("/api/settings");
        if (response.ok) {
          const settings = await response.json();
          this.settingsForm = { ...this.settingsForm, ...settings };
          console.log("📄 Loaded settings:", settings);
        }
      } catch (error) {
        console.error("❌ Failed to load settings:", error);
      }
    },

    // Load models from API
    async loadModels() {
      try {
        this.loading = true;
        console.log("📡 Loading models from API...");

        const response = await fetch("/api/models");

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Ensure we have valid data
        this.models = Array.isArray(data.models) ? data.models : [];
        this.filteredModels = [...this.models];

        console.log(`📂 Loaded ${this.models.length} models`);

        // Auto-select first model if none selected and models exist
        if (this.models.length > 0 && !this.selectedModel) {
          this.selectModel(this.models[0]);
        }

        // Filter models to update display
        this.filterModels();
      } catch (error) {
        console.error("❌ Failed to load models:", error);
        this.showNotification(
          "Failed to load models: " + error.message,
          "error"
        );
        this.models = [];
        this.filteredModels = [];
      } finally {
        this.loading = false;
      }
    },

    // Filter models based on search and type
    filterModels() {
      if (!this.models || !Array.isArray(this.models)) {
        this.filteredModels = [];
        return;
      }

      let filtered = [...this.models];

      // Apply search filter
      if (this.searchQuery && this.searchQuery.trim()) {
        const query = this.searchQuery.toLowerCase();
        filtered = filtered.filter(
          (model) =>
            (model.name && model.name.toLowerCase().includes(query)) ||
            (model.type && model.type.toLowerCase().includes(query)) ||
            (model.notes && model.notes.toLowerCase().includes(query))
        );
      }

      // Apply type filter
      if (this.selectedType && this.selectedType !== "all") {
        filtered = filtered.filter(
          (model) =>
            model.type &&
            model.type.toLowerCase() === this.selectedType.toLowerCase()
        );
      }

      this.filteredModels = filtered;
      console.log(`🔍 Filtered to ${filtered.length} models`);
    },

    // Set filter type
    setFilter(type) {
      this.selectedType = type;
      this.filterModels();
    },

    // Select a model
    async selectModel(model) {
      if (!model || !model.id) {
        console.warn("⚠️ Attempted to select invalid model:", model);
        return;
      }

      this.selectedModel = model;
      console.log(`📋 Selected model: ${model.name}`);

      // Load detailed model info if needed
      try {
        const response = await fetch(`/api/models/${model.id}`);
        if (response.ok) {
          const detailedModel = await response.json();
          this.selectedModel = detailedModel;
        }
      } catch (error) {
        console.warn("⚠️ Failed to load detailed model info:", error);
        // Continue with basic model info
      }
    },

    // Settings functions
    openSettings() {
      this.showSettings = true;
      console.log(
        "⚙️ Opening settings - showSettings is now:",
        this.showSettings
      );

      // Focus the directory input after modal opens
      setTimeout(() => {
        const input = document.querySelector(".setting-input");
        if (input) {
          input.focus();
        }
      }, 100);
    },

    closeSettings() {
      console.log("⚙️ Closing settings");
      this.showSettings = false;
      this.scanProgress.active = false;
      this.scanProgress.percent = 0;
      this.scanProgress.message = "Initializing scan...";

      // Force hide modal with direct DOM manipulation as backup
      setTimeout(() => {
        const modal = document.querySelector(".modal-overlay");
        if (modal && window.getComputedStyle(modal).display !== "none") {
          console.log("🔧 Alpine.js not hiding modal, forcing with CSS");
          modal.style.display = "none";
        }
      }, 100);
    },

    async saveSettings() {
      console.log("💾 Save Settings clicked!");
      console.log("Current settings form:", this.settingsForm);

      try {
        // Validate directory path
        if (
          !this.settingsForm.models_directory ||
          !this.settingsForm.models_directory.trim()
        ) {
          console.log("❌ No directory path provided");
          this.showNotification(
            "Please enter a models directory path",
            "error"
          );
          return;
        }

        console.log("📡 Sending settings to server...");
        this.scanProgress.active = true;
        this.scanProgress.message = "Saving settings...";
        this.scanProgress.percent = 10;

        const response = await fetch("/api/settings", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(this.settingsForm),
        });

        console.log("📡 Settings response status:", response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("❌ Settings error response:", errorText);
          throw new Error(`Server error: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log("✅ Settings saved successfully:", result);

        this.showNotification("Settings saved! Starting scan...", "success");

        // Trigger scan
        await this.scanModels();
      } catch (error) {
        console.error("❌ Failed to save settings:", error);
        this.showNotification(
          `Failed to save settings: ${error.message}`,
          "error"
        );
        this.scanProgress.active = false;
      }
    },

    async scanModels() {
      console.log("🔍 Scan Models started!");
      try {
        this.scanProgress.message = "Scanning models directory...";
        this.scanProgress.percent = 25;

        const response = await fetch("/api/scan", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            directory: this.settingsForm.models_directory,
          }),
        });

        console.log("📡 Scan response status:", response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("❌ Scan error response:", errorText);
          throw new Error(`Scan failed: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log("✅ Scan completed:", result);

        this.scanProgress.percent = 75;
        this.scanProgress.message = "Loading models into UI...";

        // Reload models
        await this.loadModels();

        this.scanProgress.percent = 100;
        this.scanProgress.message = `Found ${result.models_found} models!`;

        this.showNotification(
          `Scan complete! Found ${result.models_found} models.`,
          "success"
        );

        // Close settings after successful scan
        setTimeout(() => {
          this.closeSettings();
        }, 2000);
      } catch (error) {
        console.error("❌ Scan failed:", error);
        this.showNotification(`Scan failed: ${error.message}`, "error");
        this.scanProgress.active = false;
      }
    },

    browseDirectory() {
      console.log("📂 Browse Directory clicked!");

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

      alert(
        "Web apps cannot open file browsers.\n\nPlease manually enter your ComfyUI models directory path.\n\n" +
          examples.join("\n")
      );

      setTimeout(() => {
        const input = document.querySelector(".setting-input");
        if (input) {
          input.focus();
          input.select();
        }
      }, 100);
    },

    // Action handlers
    openFolder() {
      if (this.selectedModel) {
        console.log(`📁 Opening folder for: ${this.selectedModel.name}`);
        this.showNotification("Opening model folder...", "info");
      }
    },
    // Notes Editor Functions
    async editNotes() {
      if (!this.selectedModel) {
        this.showNotification("No model selected", "warning");
        return;
      }

      console.log(`📝 Opening notes editor for: ${this.selectedModel.name}`);

      try {
        // Load existing notes from server
        const response = await fetch(`/api/notes/${this.selectedModel.id}`);
        if (response.ok) {
          const notesData = await response.json();
          this.notesEditor.content = notesData.content || "";
          this.notesEditor.originalContent = this.notesEditor.content;
          this.notesEditor.backups = notesData.backups || [];
        } else {
          // Start with empty notes if none exist
          this.notesEditor.content = "";
          this.notesEditor.originalContent = "";
          this.notesEditor.backups = [];
        }

        this.notesEditor.isOpen = true;
        this.notesEditor.isDirty = false;
        this.notesEditor.autoSaveStatus = "saved";
        this.updateNotesStats();

        // Focus the textarea after opening
        setTimeout(() => {
          const textarea = document.getElementById("notesTextarea");
          if (textarea) {
            textarea.focus();
          }
        }, 100);
      } catch (error) {
        console.error("❌ Failed to load notes:", error);
        this.showNotification(
          "Failed to load notes: " + error.message,
          "error"
        );
      }
    },

    openCivitAI() {
      if (this.selectedModel) {
        console.log(`🌐 Opening CivitAI for: ${this.selectedModel.name}`);
        window.open("https://civitai.com", "_blank");
        this.showNotification("Opening CivitAI...", "success");
      }
    },

    copyPath() {
      if (this.selectedModel && this.selectedModel.path) {
        navigator.clipboard
          .writeText(this.selectedModel.path)
          .then(() => {
            this.showNotification("Path copied to clipboard!", "success");
          })
          .catch(() => {
            this.showNotification("Failed to copy path", "error");
          });
      }
    },

    // Gallery functions
    getExampleImage(type) {
      const imageMap = {
        portrait: this.generatePlaceholderSVG("Portrait", "512x768", 150, 200),
        full_body: this.generatePlaceholderSVG(
          "Full Body",
          "512x768",
          150,
          200
        ),
        landscape: this.generatePlaceholderSVG(
          "Landscape",
          "768x512",
          200,
          150
        ),
        closeup: this.generatePlaceholderSVG("Close-up", "512x512", 150, 150),
        art: this.generatePlaceholderSVG("Artistic", "512x768", 150, 200),
      };

      return imageMap[type] || imageMap["portrait"];
    },

    generatePlaceholderSVG(title, resolution, width, height) {
      const svg = `
        <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
          <rect width="${width}" height="${height}" fill="#44475a"/>
          <text x="50%" y="40%" fill="#f8f8f2" text-anchor="middle" dy=".3em" 
                font-family="sans-serif" font-size="12px">${title}</text>
          <text x="50%" y="60%" fill="#6272a4" text-anchor="middle" dy=".3em" 
                font-family="sans-serif" font-size="10px">${resolution}</text>
        </svg>
      `;
      return "data:image/svg+xml;base64," + btoa(svg);
    },

    viewExample(example) {
      console.log(`🖼️ Viewing example: ${example.type}`);
      this.showNotification(`Viewing ${example.type} example`, "info");
    },

    addExample() {
      if (this.selectedModel) {
        console.log(`➕ Adding example for: ${this.selectedModel.name}`);
        this.showNotification("Image upload coming soon...", "info");
      }
    },

    // ComfyUI connection check
    async checkComfyUIConnection() {
      try {
        const response = await fetch("http://localhost:8188/system_stats", {
          method: "GET",
          mode: "cors",
        });
        this.isConnected = response.ok;
      } catch (error) {
        this.isConnected = false;
        if (
          !error.message.includes("CORS") &&
          !error.message.includes("NetworkError")
        ) {
          console.warn("⚠️ ComfyUI connection check failed:", error.message);
        }
      }
    },

    // Keyboard shortcuts
    handleKeydown(event) {
      if (event.key === "Escape") {
        if (this.showSettings) {
          this.closeSettings();
        } else if (this.searchQuery) {
          this.searchQuery = "";
          this.filterModels();
        } else {
          this.selectedModel = null;
        }
      }

      if (this.showSettings) {
        if (
          event.key === "Enter" &&
          event.target.classList.contains("setting-input")
        ) {
          event.preventDefault();
          this.saveSettings();
        }
        return;
      }

      if (event.key === "F2" && this.selectedModel) {
        this.editNotes();
      }

      if (event.ctrlKey && event.key === "f") {
        event.preventDefault();
        const searchBox = document.querySelector(".search-box");
        if (searchBox) {
          searchBox.focus();
        }
      }

      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        this.navigateModels(event.key === "ArrowDown" ? 1 : -1);
      }
    },

    navigateModels(direction) {
      if (!this.filteredModels || this.filteredModels.length === 0) return;

      let currentIndex = this.selectedModel
        ? this.filteredModels.findIndex(
            (m) => m && m.id === this.selectedModel.id
          )
        : -1;

      let newIndex = currentIndex + direction;

      if (newIndex >= this.filteredModels.length) {
        newIndex = 0;
      } else if (newIndex < 0) {
        newIndex = this.filteredModels.length - 1;
      }

      if (this.filteredModels[newIndex]) {
        this.selectModel(this.filteredModels[newIndex]);
      }
    },

    // Utility functions
    showNotification(message, type = "info") {
      const toast = document.createElement("div");
      toast.className = `toast toast-${type}`;
      toast.textContent = message;

      Object.assign(toast.style, {
        position: "fixed",
        top: "20px",
        right: "20px",
        padding: "12px 20px",
        borderRadius: "6px",
        color: "#f8f8f2",
        fontWeight: "500",
        zIndex: "1000",
        opacity: "0",
        transform: "translateX(100%)",
        transition: "all 0.3s ease",
      });

      const colors = {
        success: "#50fa7b",
        error: "#ff5555",
        warning: "#ffb86c",
        info: "#8be9fd",
      };
      toast.style.backgroundColor = colors[type] || colors.info;

      document.body.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateX(0)";
      }, 100);

      setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => {
          if (document.body.contains(toast)) {
            document.body.removeChild(toast);
          }
        }, 300);
      }, 3000);
    },

    formatFileSize(bytes) {
      if (!bytes) return "Unknown";

      const sizes = ["B", "KB", "MB", "GB", "TB"];
      if (bytes === 0) return "0 B";

      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      const size = (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1);
      return `${size} ${sizes[i]}`;
    },

    formatDate(dateString) {
      if (!dateString) return "Unknown";

      try {
        const date = new Date(dateString);
        return date.toLocaleDateString();
      } catch (error) {
        return dateString;
      }
    },
  };
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 ComfyUI Model Explorer ready!");

  // Set up global keyboard shortcuts
  document.addEventListener("keydown", (event) => {
    const explorerComponent = document.querySelector(
      '[x-data="modelExplorer()"]'
    );
    if (explorerComponent && explorerComponent._x_dataStack) {
      const data = explorerComponent._x_dataStack[0];
      if (data && data.handleKeydown) {
        data.handleKeydown(event);
      }
    }
  });

  console.log("💡 Tips:");
  console.log("  - Use Ctrl+F to focus search");
  console.log("  - Use F2 to edit notes");
  console.log("  - Use arrow keys to navigate models");
  console.log("  - Use Escape to clear search/selection");
});

// Export for global access if needed
window.modelExplorer = modelExplorer;

// Simple button fix that will work immediately
setTimeout(() => {
  console.log("🔧 Setting up button fixes...");

  // Get the Alpine.js app instance
  function getApp() {
    const container = document.querySelector('[x-data="modelExplorer()"]');
    return container && container._x_dataStack
      ? container._x_dataStack[0]
      : null;
  }

  // Fix close button
  const closeBtn = document.querySelector(".modal-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const app = getApp();
      if (app && app.closeSettings) {
        app.closeSettings();
      } else {
        document.querySelector(".modal-overlay").style.display = "none";
      }
    });
  }

  // Fix cancel button
  const cancelBtn = document.querySelector(".modal-footer .btn-secondary");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const app = getApp();
      if (app && app.closeSettings) {
        app.closeSettings();
      } else {
        document.querySelector(".modal-overlay").style.display = "none";
      }
    });
  }

  // Fix save button
  const saveBtn = document.querySelector(".modal-footer .btn-primary");
  if (saveBtn) {
    saveBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const app = getApp();
      if (app && app.saveSettings) {
        app.saveSettings();
      }
    });
  }

  // Fix browse button
  const browseBtn = document.querySelector(
    ".directory-input-group .btn-secondary"
  );
  if (browseBtn) {
    browseBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const app = getApp();
      if (app && app.browseDirectory) {
        app.browseDirectory();
      }
    });
  }

  // Add this to the setTimeout block in main.js where you fix the other buttons

  // Fix notes editor buttons
  setTimeout(() => {
    console.log("🔧 Setting up notes editor button fixes...");

    // Get the Alpine.js app instance (same function as before)
    function getApp() {
      const container = document.querySelector('[x-data="modelExplorer()"]');
      return container && container._x_dataStack
        ? container._x_dataStack[0]
        : null;
    }

    // Check for notes editor elements periodically since they're in a modal
    const setupNotesEditorFixes = () => {
      // Fix notes editor close button
      const notesCloseBtn = document.querySelector(
        ".notes-editor-modal .modal-close"
      );
      if (notesCloseBtn && !notesCloseBtn._eventFixed) {
        notesCloseBtn._eventFixed = true;
        notesCloseBtn.addEventListener("click", function (e) {
          e.preventDefault();
          const app = getApp();
          if (app && app.closeNotesEditor) {
            app.closeNotesEditor();
          }
        });
      }

      // Fix notes editor cancel button
      const notesCancelBtn = document.querySelector(
        ".notes-editor-footer .btn-secondary"
      );
      if (notesCancelBtn && !notesCancelBtn._eventFixed) {
        notesCancelBtn._eventFixed = true;
        notesCancelBtn.addEventListener("click", function (e) {
          e.preventDefault();
          const app = getApp();
          if (app && app.closeNotesEditor) {
            app.closeNotesEditor();
          }
        });
      }

      // Fix notes editor save button
      const notesSaveBtn = document.querySelector(
        ".notes-editor-footer .btn-primary"
      );
      if (notesSaveBtn && !notesSaveBtn._eventFixed) {
        notesSaveBtn._eventFixed = true;
        notesSaveBtn.addEventListener("click", function (e) {
          e.preventDefault();
          const app = getApp();
          if (app && app.saveAndCloseNotes) {
            app.saveAndCloseNotes();
          }
        });
      }

      // Fix template dropdown button
      const templateBtn = document.querySelector(".template-btn");
      if (templateBtn && !templateBtn._eventFixed) {
        templateBtn._eventFixed = true;
        templateBtn.addEventListener("click", function (e) {
          e.preventDefault();
          const app = getApp();
          if (app && app.toggleTemplateDropdown) {
            app.toggleTemplateDropdown();
          }
        });
      }

      // Fix formatting buttons
      const formatBtns = document.querySelectorAll(".toolbar-btn");
      formatBtns.forEach((btn) => {
        if (!btn._eventFixed && btn.title) {
          btn._eventFixed = true;
          btn.addEventListener("click", function (e) {
            e.preventDefault();
            const app = getApp();
            if (!app) return;

            // Handle different formatting buttons based on their title
            const title = btn.title.toLowerCase();
            if (title.includes("bold")) {
              app.insertFormatting("**", "**");
            } else if (title.includes("italic")) {
              app.insertFormatting("*", "*");
            } else if (title.includes("code")) {
              app.insertFormatting("`", "`");
            } else if (title.includes("heading")) {
              app.insertFormatting("## ", "");
            } else if (title.includes("list")) {
              app.insertFormatting("- ", "");
            } else if (title.includes("separator")) {
              app.insertText("\n---\n");
            }
          });
        }
      });

      // Fix template items
      const templateItems = document.querySelectorAll(".template-item");
      templateItems.forEach((item) => {
        if (!item._eventFixed) {
          item._eventFixed = true;
          item.addEventListener("click", function (e) {
            e.preventDefault();
            const app = getApp();
            if (app && app.applyTemplate) {
              // Get template ID from the item (you'll need to add data attribute)
              const templateName =
                item.querySelector(".template-name")?.textContent;
              const templateMap = {
                "Checkpoint Model": "checkpoint",
                "LoRA Model": "lora",
                "VAE Model": "vae",
                ControlNet: "controlnet",
                Embedding: "embedding",
              };
              const templateId = templateMap[templateName];
              if (templateId) {
                app.applyTemplate(templateId);
              }
            }
          });
        }
      });
    };

    // Set up initial fixes and then check periodically for modal elements
    setupNotesEditorFixes();
    setInterval(setupNotesEditorFixes, 1000);

    console.log("✅ Notes editor button fixes applied");
  }, 1000);

  console.log("✅ Button fixes applied");
}, 1000);
