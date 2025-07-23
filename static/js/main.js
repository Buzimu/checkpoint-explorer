// Main Alpine.js data and functionality
function modelExplorer() {
  return {
    // Data
    models: [],
    filteredModels: [],
    selectedModel: null,
    searchQuery: "",
    selectedType: "all",
    isConnected: false,
    loading: false,
    showSettings: false,

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

      await this.loadSettings();
      await this.loadModels();
      this.checkComfyUIConnection();

      // Set up periodic connection check
      setInterval(() => {
        this.checkComfyUIConnection();
      }, 30000); // Check every 30 seconds

      console.log("✅ Initialization complete");
    },

    // Load settings from server
    async loadSettings() {
      try {
        const response = await fetch("/api/settings");
        const settings = await response.json();
        this.settingsForm = { ...settings };
        console.log("📄 Loaded settings:", settings);
      } catch (error) {
        console.error("❌ Failed to load settings:", error);
      }
    },

    // Load models from API
    async loadModels() {
      try {
        this.loading = true;
        const response = await fetch("/api/models");

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        this.models = Array.isArray(data.models) ? data.models : [];
        this.filteredModels = [...this.models];

        console.log(`📂 Loaded ${this.models.length} models`);

        // Auto-select first model if none selected and models exist
        if (this.models.length > 0 && !this.selectedModel) {
          this.selectModel(this.models[0]);
        }
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
      console.log("⚙️ Opening settings");
    },

    closeSettings() {
      this.showSettings = false;
      this.scanProgress.active = false;
      this.scanProgress.percent = 0;
      console.log("⚙️ Closing settings");
    },

    async saveSettings() {
      try {
        console.log("💾 Saving settings:", this.settingsForm);

        // Validate directory path
        if (!this.settingsForm.models_directory.trim()) {
          this.showNotification(
            "Please enter a models directory path",
            "error"
          );
          return;
        }

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

        console.log("📡 Settings API response status:", response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("❌ Settings API error:", errorText);
          throw new Error(`Server error: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log("✅ Settings saved:", result);

        this.showNotification("Settings saved successfully!", "success");

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
      try {
        console.log(
          "🔍 Starting scan for directory:",
          this.settingsForm.models_directory
        );

        this.scanProgress.active = true;
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

        console.log("📡 Scan API response status:", response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("❌ Scan API error:", errorText);
          throw new Error(`Scan failed: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        console.log("✅ Scan completed:", result);

        this.scanProgress.percent = 75;
        this.scanProgress.message = "Loading models...";

        // Reload models
        await this.loadModels();

        this.scanProgress.percent = 100;
        this.scanProgress.message = `Found ${result.models_found} models!`;

        this.showNotification(
          `Scan complete! Found ${result.models_found} models.`,
          "success"
        );

        // Close settings and hide progress after delay
        setTimeout(() => {
          this.closeSettings();
        }, 1000);

        setTimeout(() => {
          this.scanProgress.active = false;
          this.scanProgress.percent = 0;
        }, 2000);
      } catch (error) {
        console.error("❌ Scan failed:", error);
        this.showNotification(`Scan failed: ${error.message}`, "error");
        this.scanProgress.active = false;
      }
    },

    browseDirectory() {
      // Provide helpful path suggestions since we can't open a file browser in web app
      const suggestions = [
        "Windows: C:\\ComfyUI\\models",
        "Windows: C:\\stable-diffusion-webui\\models",
        "Mac/Linux: /path/to/ComfyUI/models",
        "Mac/Linux: ~/ComfyUI/models",
      ];

      const message =
        "File browser not available in web version.\n\nCommon paths:\n" +
        suggestions.join("\n");
      alert(message);

      // Focus the input field
      const input = document.querySelector(".setting-input");
      if (input) {
        input.focus();
      }
    },

    // Action handlers
    openFolder() {
      if (this.selectedModel) {
        console.log(`📁 Opening folder for: ${this.selectedModel.name}`);
        this.showNotification("Opening model folder...", "info");
        // TODO: Implement actual folder opening
      }
    },

    editNotes() {
      if (this.selectedModel) {
        console.log(`📝 Editing notes for: ${this.selectedModel.name}`);
        this.showNotification("Notes editor coming soon...", "info");
        // TODO: Implement notes editor
      }
    },

    openCivitAI() {
      if (this.selectedModel) {
        console.log(`🌐 Opening CivitAI for: ${this.selectedModel.name}`);
        // For now, just open CivitAI homepage
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
      // Generate placeholder images based on type
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
      // TODO: Implement full-screen image viewer
    },

    addExample() {
      if (this.selectedModel) {
        console.log(`➕ Adding example for: ${this.selectedModel.name}`);
        this.showNotification("Image upload coming soon...", "info");
        // TODO: Implement image upload
      }
    },

    // ComfyUI connection check
    async checkComfyUIConnection() {
      try {
        // Try to connect to ComfyUI's default port
        const response = await fetch("http://localhost:8188/system_stats", {
          method: "GET",
          mode: "cors",
        });
        this.isConnected = response.ok;
      } catch (error) {
        // Handle CORS and network errors gracefully
        this.isConnected = false;
        // Only log if it's not a common CORS error
        if (
          !error.message.includes("CORS") &&
          !error.message.includes("NetworkError")
        ) {
          console.warn("⚠️ ComfyUI connection check failed:", error.message);
        }
      }
    },

    // Utility functions
    showNotification(message, type = "info") {
      // Create a simple toast notification
      const toast = document.createElement("div");
      toast.className = `toast toast-${type}`;
      toast.textContent = message;

      // Style the toast
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

      // Set background color based on type
      const colors = {
        success: "#50fa7b",
        error: "#ff5555",
        warning: "#ffb86c",
        info: "#8be9fd",
      };
      toast.style.backgroundColor = colors[type] || colors.info;

      document.body.appendChild(toast);

      // Animate in
      setTimeout(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateX(0)";
      }, 100);

      // Remove after 3 seconds
      setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => {
          document.body.removeChild(toast);
        }, 300);
      }, 3000);
    },

    formatFileSize(bytes) {
      if (!bytes) return "Unknown";

      const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
      if (bytes === 0) return "0 Bytes";

      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      return (
        parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + " " + sizes[i]
      );
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

    // Keyboard shortcuts
    handleKeydown(event) {
      // Escape key - clear selection or search or close modal
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

      // Don't handle other shortcuts if modal is open
      if (this.showSettings) return;

      // F2 - Edit notes
      if (event.key === "F2" && this.selectedModel) {
        this.editNotes();
      }

      // Ctrl+F - Focus search
      if (event.ctrlKey && event.key === "f") {
        event.preventDefault();
        const searchBox = document.querySelector(".search-box");
        if (searchBox) {
          searchBox.focus();
        }
      }

      // Arrow keys for model navigation
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
  };
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 ComfyUI Model Explorer ready!");

  // Set up global keyboard shortcuts
  document.addEventListener("keydown", (event) => {
    // Get the Alpine.js component instance
    const explorerComponent = document.querySelector(
      '[x-data="modelExplorer()"]'
    );
    if (explorerComponent && explorerComponent._x_dataStack) {
      const data = explorerComponent._x_dataStack[0];
      data.handleKeydown(event);
    }
  });

  // Add some helpful console messages
  console.log("💡 Tips:");
  console.log("  - Use Ctrl+F to focus search");
  console.log("  - Use F2 to edit notes");
  console.log("  - Use arrow keys to navigate models");
  console.log("  - Use Escape to clear search/selection");
});

// Export for global access if needed
window.modelExplorer = modelExplorer;
