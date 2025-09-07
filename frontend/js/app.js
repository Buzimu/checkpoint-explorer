/**
 * ComfyUI Model Explorer - Main Application
 * Clean architecture without Alpine.js complications
 */

import { Store } from "./state/store.js";
import { ModelList } from "./components/modelList.js";
import { ModelDetails } from "./components/modelDetails.js";
import { SearchBar } from "./components/search.js";
import { SettingsModal } from "./components/settings.js";
import { NotesEditor } from "./components/notesEditor.js";
import { StatusBar } from "./components/statusBar.js";
import { API } from "./services/api.js";
import { NotificationService } from "./services/notifications.js";
import { KeyboardService } from "./services/keyboard.js";

class ModelExplorerApp {
  constructor() {
    this.store = new Store();
    this.api = new API();
    this.notifications = new NotificationService();
    this.keyboard = new KeyboardService();
    this.components = {};
  }

  async init() {
    console.log("🎨 ComfyUI Model Explorer v2.0 initializing...");

    try {
      // Initialize components
      this.initializeComponents();

      // Load initial data
      await this.loadInitialData();

      // Set up event listeners
      this.setupEventListeners();

      // Set up keyboard shortcuts
      this.setupKeyboardShortcuts();

      // Check ComfyUI connection
      this.checkComfyUIConnection();

      // Set up periodic tasks
      this.setupPeriodicTasks();

      console.log("✅ Application initialized successfully");
    } catch (error) {
      console.error("❌ Failed to initialize application:", error);
      this.notifications.error("Failed to initialize application");
    }
  }

  initializeComponents() {
    // Initialize all components with their DOM containers
    this.components = {
      modelList: new ModelList(
        document.querySelector(".models-list"),
        this.store,
        this.api
      ),

      modelDetails: new ModelDetails(
        document.querySelector(".content-area"),
        this.store,
        this.api
      ),

      searchBar: new SearchBar(
        document.querySelector(".filter-section"),
        this.store
      ),

      settingsModal: new SettingsModal(
        document.getElementById("settings-modal"),
        this.store,
        this.api
      ),

      notesEditor: new NotesEditor(
        document.getElementById("notes-editor-modal"),
        this.store,
        this.api
      ),

      statusBar: new StatusBar(
        document.querySelector(".status-bar"),
        this.store
      ),
    };

    console.log("📦 Components initialized");
  }

  async loadInitialData() {
    try {
      // Load settings
      const settings = await this.api.getSettings();
      this.store.setState({ settings });

      // Load models if directory is configured
      if (settings.models_directory) {
        const modelsData = await this.api.getModels();
        this.store.setState({
          models: modelsData.models,
          totalModels: modelsData.total,
        });

        // Auto-select first model if none selected
        if (modelsData.models.length > 0 && !this.store.state.selectedModel) {
          this.store.setState({ selectedModel: modelsData.models[0] });
        }
      }

      console.log(`📊 Loaded ${this.store.state.models.length} models`);
    } catch (error) {
      console.error("Failed to load initial data:", error);
      this.notifications.warning(
        "Failed to load models. Please configure your models directory."
      );
    }
  }

  setupEventListeners() {
    // Global event listeners

    // Handle window resize
    window.addEventListener("resize", () => {
      this.handleResize();
    });

    // Handle online/offline
    window.addEventListener("online", () => {
      this.notifications.success("Connection restored");
      this.checkComfyUIConnection();
    });

    window.addEventListener("offline", () => {
      this.notifications.warning("Connection lost");
    });

    // Custom events from components
    document.addEventListener("model:selected", (event) => {
      this.handleModelSelection(event.detail);
    });

    document.addEventListener("settings:open", () => {
      this.components.settingsModal.open();
    });

    document.addEventListener("notes:edit", () => {
      if (this.store.state.selectedModel) {
        this.components.notesEditor.open(this.store.state.selectedModel);
      }
    });

    document.addEventListener("scan:start", async (event) => {
      await this.startScan(event.detail);
    });

    setInterval(() => {
      const settingsBtn = document.getElementById("settings-btn");
      if (settingsBtn && !settingsBtn._listenerAttached) {
        settingsBtn._listenerAttached = true;
        settingsBtn.addEventListener("click", () => {
          this.components.settingsModal.open();
        });
      }

      const configureBtn = document.getElementById("configure-btn");
      if (configureBtn && !configureBtn._listenerAttached) {
        configureBtn._listenerAttached = true;
        configureBtn.addEventListener("click", () => {
          this.components.settingsModal.open();
        });
      }
    }, 500);

    console.log("🎯 Event listeners configured");
  }

  setupKeyboardShortcuts() {
    // Global keyboard shortcuts
    this.keyboard.register("ctrl+f", () => {
      this.components.searchBar.focus();
    });

    this.keyboard.register("f2", () => {
      if (this.store.state.selectedModel) {
        this.components.notesEditor.open(this.store.state.selectedModel);
      }
    });

    this.keyboard.register("escape", () => {
      // Clear search if active
      if (this.store.state.filters.search) {
        this.store.setState({
          filters: { ...this.store.state.filters, search: "" },
        });
      }
      // Close modals
      else if (this.components.settingsModal.isOpen) {
        this.components.settingsModal.close();
      } else if (this.components.notesEditor.isOpen) {
        this.components.notesEditor.close();
      }
      // Clear selection
      else if (this.store.state.selectedModel) {
        this.store.setState({ selectedModel: null });
      }
    });

    this.keyboard.register("arrowdown", () => {
      this.navigateModels(1);
    });

    this.keyboard.register("arrowup", () => {
      this.navigateModels(-1);
    });

    this.keyboard.register("ctrl+s", (e) => {
      e.preventDefault();
      if (this.components.notesEditor.isOpen) {
        this.components.notesEditor.save();
      }
    });

    console.log("⌨️ Keyboard shortcuts registered");
  }

  setupPeriodicTasks() {
    // Check ComfyUI connection every 30 seconds
    setInterval(() => {
      this.checkComfyUIConnection();
    }, 30000);

    // Auto-save drafts every 5 seconds if notes editor is open
    setInterval(() => {
      if (
        this.components.notesEditor.isOpen &&
        this.components.notesEditor.isDirty
      ) {
        this.components.notesEditor.autoSave();
      }
    }, 5000);
  }

  async checkComfyUIConnection() {
    try {
      const response = await fetch("http://localhost:8188/system_stats", {
        method: "GET",
        mode: "cors",
      });

      const isConnected = response.ok;
      this.store.setState({ comfyUIConnected: isConnected });
    } catch (error) {
      this.store.setState({ comfyUIConnected: false });
    }
  }

  handleModelSelection(model) {
    this.store.setState({ selectedModel: model });

    // Scroll model into view in the list
    const modelElement = document.querySelector(
      `[data-model-id="${model.id}"]`
    );
    if (modelElement) {
      modelElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  navigateModels(direction) {
    const models = this.getFilteredModels();
    if (models.length === 0) return;

    let currentIndex = -1;
    if (this.store.state.selectedModel) {
      currentIndex = models.findIndex(
        (m) => m.id === this.store.state.selectedModel.id
      );
    }

    let newIndex = currentIndex + direction;

    // Wrap around
    if (newIndex >= models.length) {
      newIndex = 0;
    } else if (newIndex < 0) {
      newIndex = models.length - 1;
    }

    this.handleModelSelection(models[newIndex]);
  }

  getFilteredModels() {
    let models = [...this.store.state.models];
    const filters = this.store.state.filters;

    // Apply search filter
    if (filters.search) {
      const search = filters.search.toLowerCase();
      models = models.filter(
        (m) =>
          m.name.toLowerCase().includes(search) ||
          m.type.toLowerCase().includes(search) ||
          (m.notes_content && m.notes_content.toLowerCase().includes(search))
      );
    }

    // Apply type filter
    if (filters.type && filters.type !== "all") {
      models = models.filter(
        (m) => m.type.toLowerCase() === filters.type.toLowerCase()
      );
    }

    return models;
  }

  async startScan(directory) {
    try {
      this.store.setState({ scanning: true });

      const result = await this.api.startScan(directory);

      if (result.status === "success") {
        this.notifications.success("Scan started successfully");

        // Poll for scan status
        this.pollScanStatus();
      }
    } catch (error) {
      console.error("Failed to start scan:", error);
      this.notifications.error("Failed to start scan: " + error.message);
      this.store.setState({ scanning: false });
    }
  }

  async pollScanStatus() {
    const pollInterval = setInterval(async () => {
      try {
        const status = await this.api.getScanStatus();

        this.store.setState({ scanProgress: status.scan });

        if (!status.scan.active) {
          clearInterval(pollInterval);
          this.store.setState({ scanning: false });

          // Reload models
          await this.loadInitialData();

          this.notifications.success("Scan completed successfully");
        }
      } catch (error) {
        clearInterval(pollInterval);
        this.store.setState({ scanning: false });
        console.error("Failed to get scan status:", error);
      }
    }, 1000);
  }

  handleResize() {
    // Handle responsive layout changes
    const width = window.innerWidth;

    if (width < 768) {
      document.body.classList.add("mobile");
    } else {
      document.body.classList.remove("mobile");
    }
  }
}

// Initialize app when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.modelExplorer = new ModelExplorerApp();
  window.modelExplorer.init();
});

// Export for testing
export { ModelExplorerApp };
