/**
 * Central state management store
 * Simple, predictable state management without external dependencies
 */

export class Store {
  constructor() {
    // Initial state
    this.state = {
      // Models data
      models: [],
      selectedModel: null,
      totalModels: 0,

      // Filters
      filters: {
        search: "",
        type: "all",
        hasNotes: null,
        tags: [],
      },

      // UI state
      ui: {
        sidebarCollapsed: false,
        settingsOpen: false,
        notesEditorOpen: false,
        scanModalOpen: false,
        loading: false,
        scanning: false,
      },

      // Settings
      settings: {
        models_directory: "",
        auto_scan: true,
        theme: "dark",
        show_examples: true,
        scan_recursive: true,
        last_scan: null,
      },

      // Scan progress
      scanProgress: {
        active: false,
        progress: 0,
        total: 0,
        current_file: "",
        message: "",
      },

      // System status
      comfyUIConnected: false,
      statistics: {
        total_models: 0,
        by_type: {},
        with_notes: 0,
        total_size_gb: 0,
      },
    };

    // Subscribers
    this.listeners = new Set();

    // State history for undo/redo
    this.history = [];
    this.historyIndex = -1;
    this.maxHistory = 50;

    // Debounce timer
    this.debounceTimer = null;
  }

  /**
   * Update state and notify listeners
   * @param {Object} updates - Partial state updates
   * @param {Object} options - Update options
   */
  setState(updates, options = {}) {
    const { silent = false, debounce = 0, history = true } = options;

    // Clear existing debounce timer
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    // Apply debounce if specified
    if (debounce > 0) {
      this.debounceTimer = setTimeout(() => {
        this._applyStateUpdate(updates, silent, history);
      }, debounce);
    } else {
      this._applyStateUpdate(updates, silent, history);
    }
  }

  _applyStateUpdate(updates, silent, addToHistory) {
    // Store previous state for history
    const prevState = this.deepClone(this.state);

    // Deep merge updates into state
    this.state = this.deepMerge(this.state, updates);

    // Add to history if enabled
    if (addToHistory && !this.deepEqual(prevState, this.state)) {
      this.addToHistory(prevState);
    }

    // Notify listeners unless silent
    if (!silent) {
      this.notify(updates);
    }

    // Log state change in development
    if (this.isDebug()) {
      console.log("State updated:", updates);
    }
  }

  /**
   * Get current state or specific path
   * @param {string} path - Optional dot-notation path (e.g., 'ui.loading')
   */
  getState(path = null) {
    if (!path) {
      return this.deepClone(this.state);
    }

    const keys = path.split(".");
    let value = this.state;

    for (const key of keys) {
      value = value[key];
      if (value === undefined) {
        return undefined;
      }
    }

    return this.deepClone(value);
  }

  /**
   * Subscribe to state changes
   * @param {Function} listener - Callback function
   * @returns {Function} Unsubscribe function
   */
  subscribe(listener) {
    this.listeners.add(listener);

    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Notify all listeners of state change
   * @param {Object} changes - What changed
   */
  notify(changes) {
    this.listeners.forEach((listener) => {
      try {
        listener(this.state, changes);
      } catch (error) {
        console.error("Error in state listener:", error);
      }
    });
  }

  /**
   * Add state to history
   * @param {Object} state - State to add
   */
  addToHistory(state) {
    // Remove any states after current index
    this.history = this.history.slice(0, this.historyIndex + 1);

    // Add new state
    this.history.push(state);

    // Limit history size
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    } else {
      this.historyIndex++;
    }
  }

  /**
   * Undo last state change
   */
  undo() {
    if (this.historyIndex > 0) {
      this.historyIndex--;
      this.state = this.deepClone(this.history[this.historyIndex]);
      this.notify({ undo: true });
    }
  }

  /**
   * Redo state change
   */
  redo() {
    if (this.historyIndex < this.history.length - 1) {
      this.historyIndex++;
      this.state = this.deepClone(this.history[this.historyIndex]);
      this.notify({ redo: true });
    }
  }

  /**
   * Reset state to initial values
   */
  reset() {
    this.state = {
      models: [],
      selectedModel: null,
      totalModels: 0,
      filters: {
        search: "",
        type: "all",
        hasNotes: null,
        tags: [],
      },
      ui: {
        sidebarCollapsed: false,
        settingsOpen: false,
        notesEditorOpen: false,
        scanModalOpen: false,
        loading: false,
        scanning: false,
      },
      settings: this.state.settings, // Preserve settings
      scanProgress: {
        active: false,
        progress: 0,
        total: 0,
        current_file: "",
        message: "",
      },
      comfyUIConnected: false,
      statistics: {
        total_models: 0,
        by_type: {},
        with_notes: 0,
        total_size_gb: 0,
      },
    };

    this.history = [];
    this.historyIndex = -1;
    this.notify({ reset: true });
  }

  /**
   * Computed values based on state
   */
  get computed() {
    return {
      // Filtered models based on current filters
      filteredModels: () => {
        let models = [...this.state.models];
        const filters = this.state.filters;

        // Apply search
        if (filters.search) {
          const search = filters.search.toLowerCase();
          models = models.filter(
            (m) =>
              m.name.toLowerCase().includes(search) ||
              m.type.toLowerCase().includes(search) ||
              (m.notes_content &&
                m.notes_content.toLowerCase().includes(search))
          );
        }

        // Apply type filter
        if (filters.type && filters.type !== "all") {
          models = models.filter(
            (m) => m.type.toLowerCase() === filters.type.toLowerCase()
          );
        }

        // Apply has notes filter
        if (filters.hasNotes !== null) {
          models = models.filter((m) => m.has_notes === filters.hasNotes);
        }

        // Apply tag filters
        if (filters.tags && filters.tags.length > 0) {
          models = models.filter((m) => {
            if (!m.tags || m.tags.length === 0) return false;
            return filters.tags.some((tag) => m.tags.includes(tag));
          });
        }

        return models;
      },

      // Model types with counts
      modelTypes: () => {
        const types = {};
        this.state.models.forEach((model) => {
          const type = model.type || "Unknown";
          types[type] = (types[type] || 0) + 1;
        });
        return types;
      },

      // Whether we have unsaved changes
      hasUnsavedChanges: () => {
        // Check if notes editor has unsaved changes
        // This would be tracked by the NotesEditor component
        return false;
      },

      // Can undo/redo
      canUndo: () => this.historyIndex > 0,
      canRedo: () => this.historyIndex < this.history.length - 1,
    };
  }

  /**
   * Utility: Deep clone an object
   */
  deepClone(obj) {
    if (obj === null || typeof obj !== "object") {
      return obj;
    }

    if (obj instanceof Date) {
      return new Date(obj.getTime());
    }

    if (obj instanceof Array) {
      return obj.map((item) => this.deepClone(item));
    }

    if (obj instanceof Object) {
      const clonedObj = {};
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          clonedObj[key] = this.deepClone(obj[key]);
        }
      }
      return clonedObj;
    }
  }

  /**
   * Utility: Deep merge objects
   */
  deepMerge(target, source) {
    const output = { ...target };

    if (this.isObject(target) && this.isObject(source)) {
      Object.keys(source).forEach((key) => {
        if (this.isObject(source[key])) {
          if (!(key in target)) {
            output[key] = source[key];
          } else {
            output[key] = this.deepMerge(target[key], source[key]);
          }
        } else {
          output[key] = source[key];
        }
      });
    }

    return output;
  }

  /**
   * Utility: Check if value is an object
   */
  isObject(item) {
    return item && typeof item === "object" && !Array.isArray(item);
  }

  /**
   * Utility: Deep equality check
   */
  deepEqual(a, b) {
    if (a === b) return true;

    if (a == null || b == null) return false;

    if (typeof a !== typeof b) return false;

    if (typeof a !== "object") return a === b;

    const keysA = Object.keys(a);
    const keysB = Object.keys(b);

    if (keysA.length !== keysB.length) return false;

    for (const key of keysA) {
      if (!keysB.includes(key)) return false;
      if (!this.deepEqual(a[key], b[key])) return false;
    }

    return true;
  }

  /**
   * Check if in debug mode
   */
  isDebug() {
    return (
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    );
  }

  /**
   * Persist state to localStorage
   */
  persist() {
    try {
      const stateToSave = {
        filters: this.state.filters,
        ui: this.state.ui,
        settings: this.state.settings,
      };
      localStorage.setItem("modelExplorerState", JSON.stringify(stateToSave));
    } catch (error) {
      console.error("Failed to persist state:", error);
    }
  }

  /**
   * Restore state from localStorage
   */
  restore() {
    try {
      const saved = localStorage.getItem("modelExplorerState");
      if (saved) {
        const restored = JSON.parse(saved);
        this.setState(restored, { silent: true, history: false });
      }
    } catch (error) {
      console.error("Failed to restore state:", error);
    }
  }
}
