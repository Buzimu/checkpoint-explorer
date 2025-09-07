/**
 * ModelDetails Component - Displays detailed information about selected model
 */
export class ModelDetails {
  constructor(container, store, api) {
    this.container = container;
    this.store = store;
    this.api = api;
    this.currentModel = null;

    // Subscribe to store changes
    this.store.subscribe((state, changes) => {
      if (changes.selectedModel !== undefined) {
        this.render(state.selectedModel);
      }
    });

    // Initial render
    this.render(this.store.getState("selectedModel"));
  }

  render(model) {
    this.currentModel = model;

    if (!model) {
      this.renderWelcomeScreen();
      return;
    }

    this.container.innerHTML = `
      <div class="model-details-content">
        <div class="info-grid">
          <div class="info-card">
            <h3>📊 Model Information</h3>
            <div class="info-item">
              <span class="info-label">File Size</span>
              <span class="info-value">${
                model.size_formatted || model.size || "Unknown"
              }</span>
            </div>
            <div class="info-item">
              <span class="info-label">Format</span>
              <span class="info-value">${model.format || "Unknown"}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Base Model</span>
              <span class="info-value">${model.base_model || "Unknown"}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Created</span>
              <span class="info-value">${this.formatDate(
                model.created_at
              )}</span>
            </div>
          </div>
          
          <div class="info-card">
            <h3>⚙️ Quick Info</h3>
            <div class="info-item">
              <span class="info-label">Type</span>
              <span class="info-value">${model.type || "Unknown"}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Has Notes</span>
              <span class="info-value">${model.has_notes ? "Yes" : "No"}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Hash</span>
              <span class="info-value hash-value" title="${
                model.hash || "Click to generate"
              }">
                ${
                  model.hash
                    ? this.truncateHash(model.hash)
                    : '<button class="generate-hash-btn">Generate</button>'
                }
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">Path</span>
              <span class="info-value model-path" title="Click to copy">
                ${this.truncatePath(model.path)}
              </span>
            </div>
          </div>
        </div>
        
        ${this.renderGallerySection(model)}
        ${this.renderNotesSection(model)}
        ${this.renderTagsSection(model)}
      </div>
    `;

    this.attachEvents();

    // Update action buttons in top bar
    this.updateActionButtons(model);
  }

  renderWelcomeScreen() {
    const state = this.store.getState();
    const models = state.models || [];
    const hasModels = models.length > 0;

    this.container.innerHTML = `
      <div class="welcome-screen">
        <h2>Welcome to ComfyUI Model Explorer</h2>
        ${
          hasModels
            ? `
          <p>Select a model from the sidebar to view its details, examples, and notes.</p>
        `
            : `
          <p>Get started by configuring your ComfyUI models directory to scan and organize your collection.</p>
          <button class="btn btn-primary" id="welcome-settings-btn">
            📂 Configure Models Directory
          </button>
        `
        }
        <div class="stats">
          <div class="stat-item">
            <span class="stat-number">${models.length}</span>
            <span class="stat-label">Models Found</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">${
              models.filter((m) => m.has_notes).length
            }</span>
            <span class="stat-label">With Notes</span>
          </div>
          <div class="stat-item">
            <span class="stat-number">${
              Object.keys(state.statistics?.by_type || {}).length
            }</span>
            <span class="stat-label">Types</span>
          </div>
        </div>
      </div>
    `;

    // Attach welcome screen events
    const settingsBtn = this.container.querySelector("#welcome-settings-btn");
    if (settingsBtn) {
      settingsBtn.addEventListener("click", () => {
        document.dispatchEvent(new CustomEvent("settings:open"));
      });
    }

    // Update action buttons for no selection state
    this.updateActionButtons(null);
  }

  renderGallerySection(model) {
    // Placeholder for future image gallery
    return `
      <div class="gallery-section" style="display: none;">
        <h3>🖼️ Example Images</h3>
        <div class="gallery-grid">
          <!-- Future: Add example images here -->
        </div>
      </div>
    `;
  }

  renderNotesSection(model) {
    const hasNotes = model.has_notes && model.notes_content;

    return `
      <div class="notes-section">
        <h3>📝 Notes & Documentation</h3>
        ${
          hasNotes
            ? `
          <div class="notes-content">
            <pre>${this.escapeHtml(model.notes_content)}</pre>
          </div>
          <button class="btn btn-secondary edit-notes-btn">Edit Notes</button>
        `
            : `
          <div class="notes-empty">
            <p>No notes available for this model.</p>
            <button class="btn btn-secondary add-notes-btn">Add Notes</button>
          </div>
        `
        }
      </div>
    `;
  }

  renderTagsSection(model) {
    const tags = model.tags || [];

    return `
      <div class="tags-section">
        <h3>🏷️ Tags</h3>
        <div class="tags-container">
          ${tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}
          <button class="add-tag-btn" title="Add tag">+</button>
        </div>
      </div>
    `;
  }

  updateActionButtons(model) {
    const actionButtons = document.getElementById("action-buttons");
    if (!actionButtons) return;

    // If no model selected, show configure button
    if (!model) {
      actionButtons.innerHTML = `
        <button class="btn btn-primary" id="configure-btn">
          ⚙️ Configure Models Directory
        </button>
      `;

      // Attach event for configure button
      const configBtn = document.getElementById("configure-btn");
      if (configBtn) {
        configBtn.addEventListener("click", () => {
          document.dispatchEvent(new CustomEvent("settings:open"));
        });
      }
      return;
    }

    actionButtons.innerHTML = `
      <button class="btn btn-secondary" id="open-folder-btn" title="Open model folder">
        📁 Open Folder
      </button>
      <button class="btn btn-secondary" id="copy-path-btn" title="Copy full path">
        📋 Copy Path
      </button>
      ${
        model.has_notes
          ? `
        <button class="btn btn-primary" id="edit-notes-action-btn">
          ✏️ Edit Notes
        </button>
      `
          : `
        <button class="btn btn-primary" id="add-notes-action-btn">
          ➕ Add Notes
        </button>
      `
      }
      <button class="btn btn-secondary" id="refresh-btn" title="Refresh model info">
        🔄 Refresh
      </button>
    `;

    // Attach action button events
    this.attachActionButtonEvents();
  }

  attachEvents() {
    // Copy path on click
    const pathElement = this.container.querySelector(".model-path");
    if (pathElement) {
      pathElement.addEventListener("click", () => {
        this.copyToClipboard(this.currentModel.path);
      });
    }

    // Generate hash button
    const generateHashBtn = this.container.querySelector(".generate-hash-btn");
    if (generateHashBtn) {
      generateHashBtn.addEventListener("click", async () => {
        await this.generateHash();
      });
    }

    // Notes buttons
    const editNotesBtn = this.container.querySelector(".edit-notes-btn");
    const addNotesBtn = this.container.querySelector(".add-notes-btn");

    if (editNotesBtn) {
      editNotesBtn.addEventListener("click", () => {
        document.dispatchEvent(new CustomEvent("notes:edit"));
      });
    }

    if (addNotesBtn) {
      addNotesBtn.addEventListener("click", () => {
        document.dispatchEvent(new CustomEvent("notes:edit"));
      });
    }

    // Add tag button
    const addTagBtn = this.container.querySelector(".add-tag-btn");
    if (addTagBtn) {
      addTagBtn.addEventListener("click", () => {
        this.promptAddTag();
      });
    }
  }

  attachActionButtonEvents() {
    const openFolderBtn = document.getElementById("open-folder-btn");
    const copyPathBtn = document.getElementById("copy-path-btn");
    const editNotesBtn = document.getElementById("edit-notes-action-btn");
    const addNotesBtn = document.getElementById("add-notes-action-btn");
    const refreshBtn = document.getElementById("refresh-btn");

    if (openFolderBtn) {
      openFolderBtn.addEventListener("click", () => {
        this.openFolder();
      });
    }

    if (copyPathBtn) {
      copyPathBtn.addEventListener("click", () => {
        this.copyToClipboard(this.currentModel.path);
      });
    }

    if (editNotesBtn || addNotesBtn) {
      const btn = editNotesBtn || addNotesBtn;
      btn.addEventListener("click", () => {
        document.dispatchEvent(new CustomEvent("notes:edit"));
      });
    }

    if (refreshBtn) {
      refreshBtn.addEventListener("click", async () => {
        await this.refreshModel();
      });
    }
  }

  async generateHash() {
    if (!this.currentModel) return;

    try {
      const btn = this.container.querySelector(".generate-hash-btn");
      if (btn) {
        btn.textContent = "Generating...";
        btn.disabled = true;
      }

      const result = await this.api.generateModelHash(this.currentModel.id);

      if (result.hash) {
        // Update the model in store
        const models = this.store.getState("models");
        const updatedModels = models.map((m) =>
          m.id === this.currentModel.id ? { ...m, hash: result.hash } : m
        );
        this.store.setState({ models: updatedModels });

        // Re-render the hash value
        const hashElement = this.container.querySelector(".hash-value");
        if (hashElement) {
          hashElement.innerHTML = this.truncateHash(result.hash);
          hashElement.title = result.hash;
        }
      }
    } catch (error) {
      console.error("Failed to generate hash:", error);
      alert("Failed to generate hash: " + error.message);
    }
  }

  async refreshModel() {
    if (!this.currentModel) return;

    try {
      const model = await this.api.getModel(this.currentModel.id);

      // Update in store
      const models = this.store.getState("models");
      const updatedModels = models.map((m) =>
        m.id === model.model.id ? model.model : m
      );

      this.store.setState({
        models: updatedModels,
        selectedModel: model.model,
      });
    } catch (error) {
      console.error("Failed to refresh model:", error);
    }
  }

  openFolder() {
    // This would need Electron IPC to work properly
    // For now, just show the path
    if (this.currentModel) {
      const folderPath = this.currentModel.path.substring(
        0,
        this.currentModel.path.lastIndexOf("/")
      );
      alert(
        `Model folder:\n${folderPath}\n\n(Folder opening requires desktop app integration)`
      );
    }
  }

  copyToClipboard(text) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        // Show notification
        const event = new CustomEvent("notification:show", {
          detail: { message: "Copied to clipboard!", type: "success" },
        });
        document.dispatchEvent(event);
      })
      .catch(() => {
        // Fallback
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      });
  }

  promptAddTag() {
    const tagName = prompt("Enter tag name:");
    if (tagName && tagName.trim()) {
      this.addTag(tagName.trim());
    }
  }

  async addTag(tagName) {
    if (!this.currentModel) return;

    try {
      await this.api.addModelTag(this.currentModel.id, tagName);

      // Update model in store
      const models = this.store.getState("models");
      const updatedModels = models.map((m) => {
        if (m.id === this.currentModel.id) {
          const tags = m.tags || [];
          if (!tags.includes(tagName)) {
            tags.push(tagName);
          }
          return { ...m, tags };
        }
        return m;
      });

      this.store.setState({ models: updatedModels });

      // Re-render tags section
      this.render(this.currentModel);
    } catch (error) {
      console.error("Failed to add tag:", error);
    }
  }

  formatDate(dateString) {
    if (!dateString) return "Unknown";

    try {
      const date = new Date(dateString);
      return date.toLocaleDateString();
    } catch {
      return dateString;
    }
  }

  truncateHash(hash) {
    if (!hash) return "";
    return hash.substring(0, 8) + "...";
  }

  truncatePath(path) {
    if (!path) return "Unknown";
    if (path.length <= 50) return path;

    const parts = path.split(/[/\\]/);
    return ".../" + parts.slice(-2).join("/");
  }

  escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}
