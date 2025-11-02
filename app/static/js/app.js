// ComfyUI Model Explorer - Main Application
class ModelExplorer {
  constructor() {
    this.modelData = null;
    this.filteredModels = [];
    this.selectedModel = null;
    this.contentRating = "pg";
    this.isDirty = false;
    this.serverMode = true;
    this.showVideos = false;
    this.pendingMerge = null;

    // NEW: Default filter configuration
    this.DEFAULT_FILTERS = {
      types: [
        "checkpoint",
        "lora",
        "controlnet",
        "upscaler",
        "vae",
        "embedding",
        "hypernetwork",
      ],
      baseModels: [
        "SD1.5",
        "SDXL",
        "Flux",
        "Pony",
        "Illustrious",
        "WAN21",
        "WAN22",
      ],
      contentRating: "pg",
      showVideos: false,
      favoritesOnly: false,
      hasImagesOnly: false,
    };

    this.init();
  }

  init() {
    // Setup event listeners
    document.getElementById("loadJsonBtn").addEventListener("click", () => {
      this.loadFromServer();
    });

    document.getElementById("exportJsonBtn").addEventListener("click", () => {
      this.exportJson();
    });

    document.getElementById("importJsonBtn").addEventListener("click", () => {
      this.openImportModal();
    });

    document
      .getElementById("contentRatingSelect")
      .addEventListener("change", (e) => {
        this.contentRating = e.target.value;
        this.applyContentRating();
      });

    document.getElementById("videoToggle").addEventListener("click", () => {
      this.toggleVideoMode();
    });

    // Search and filter listeners
    document.getElementById("searchInput").addEventListener("input", () => {
      this.applyFilters();
    });

    // NEW: Type checkbox listeners (REMOVE old typeFilter dropdown listener)
    document
      .querySelectorAll('#typeCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.addEventListener("change", () => {
          this.applyFilters();
        });
      });

    // NEW: Base model checkbox listeners (REMOVE old baseModelFilter dropdown listener)
    document
      .querySelectorAll('#baseCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.addEventListener("change", () => {
          this.applyFilters();
        });
      });

    document
      .getElementById("favoritesFilter")
      .addEventListener("change", () => {
        this.applyFilters();
      });

    document
      .getElementById("hasImagesFilter")
      .addEventListener("change", () => {
        this.applyFilters();
      });

    // Modal close
    document.getElementById("closeEditModal").addEventListener("click", () => {
      this.closeEditModal();
    });

    // Image lightbox close
    const lightbox = document.getElementById("imageLightbox");
    if (lightbox) {
      lightbox.addEventListener("click", (e) => {
        if (
          e.target === lightbox ||
          e.target.classList.contains("lightbox-close")
        ) {
          this.closeLightbox();
        }
      });
    }

    // Keyboard shortcuts
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.closeEditModal();
        this.closeLightbox();
      }
    });

    // NEW: Reset filters to defaults on load (BEFORE loadFromServer)
    this.resetFiltersToDefaults();

    // Setup drag and drop
    this.setupDragDrop();

    // Auto-load from server
    this.loadFromServer();
  }

  resetFiltersToDefaults() {
    console.log("🔧 Resetting filters to defaults...");

    // Set all type checkboxes to checked
    this.DEFAULT_FILTERS.types.forEach((type) => {
      const checkbox = document.querySelector(
        `#typeCheckboxes input[value="${type}"]`
      );
      if (checkbox) checkbox.checked = true;
    });

    // Set all base model checkboxes to checked
    this.DEFAULT_FILTERS.baseModels.forEach((base) => {
      const checkbox = document.querySelector(
        `#baseCheckboxes input[value="${base}"]`
      );
      if (checkbox) checkbox.checked = true;
    });

    // Set content rating
    document.getElementById("contentRatingSelect").value =
      this.DEFAULT_FILTERS.contentRating;
    this.contentRating = this.DEFAULT_FILTERS.contentRating;

    // Set video toggle
    this.showVideos = this.DEFAULT_FILTERS.showVideos;
    const videoBtn = document.getElementById("videoToggle");
    videoBtn.innerHTML = "🖼️ Images";
    videoBtn.title = "Showing images only (click to include videos)";

    // Set other filters
    document.getElementById("favoritesFilter").checked =
      this.DEFAULT_FILTERS.favoritesOnly;
    document.getElementById("hasImagesFilter").checked =
      this.DEFAULT_FILTERS.hasImagesOnly;

    console.log("✅ Filters reset to defaults");
  }

  selectAllTypes() {
    document
      .querySelectorAll('#typeCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.checked = true;
      });
    this.applyFilters();
  }

  clearAllTypes() {
    document
      .querySelectorAll('#typeCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.checked = false;
      });
    this.applyFilters();
  }

  selectAllBases() {
    document
      .querySelectorAll('#baseCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.checked = true;
      });
    this.applyFilters();
  }

  clearAllBases() {
    document
      .querySelectorAll('#baseCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.checked = false;
      });
    this.applyFilters();
  }

  async loadFromServer() {
    try {
      const response = await fetch("/api/models");
      if (!response.ok) throw new Error("Failed to load from server");

      const data = await response.json();
      this.modelData = data;
      this.mergeHighLowVariants(); // Merge HIGH/LOW variants
      this.isDirty = false;
      this.processModels();
      this.renderModelGrid();
      this.updateModelCount();

      // Enable export button
      const exportBtn = document.getElementById("exportJsonBtn");
      exportBtn.disabled = false;
      exportBtn.textContent = "💾 Export JSON";
      exportBtn.title = "Export database to file";

      // Hide welcome screen
      const welcomeScreen = document.getElementById("welcomeScreen");
      if (welcomeScreen) {
        welcomeScreen.remove();
      }

      console.log(
        "✅ Loaded from server:",
        Object.keys(data.models).length,
        "models"
      );
      this.showToast("✅ Database loaded from server!");
    } catch (error) {
      console.error("Failed to load from server:", error);
      this.showToast("❌ Failed to connect to server");
    }
  }

  mergeHighLowVariants() {
    if (!this.modelData || !this.modelData.models) return;

    const models = this.modelData.models;
    const toMerge = {};
    const toDelete = [];

    // Find HIGH/LOW pairs
    Object.keys(models).forEach((path) => {
      if (path.includes("HIGH")) {
        const lowPath = path.replace("HIGH", "LOW");
        const basePath = path.replace("HIGH", "");

        if (models[lowPath]) {
          // Found a pair!
          toMerge[basePath] = {
            high: path,
            low: lowPath,
          };
          toDelete.push(path, lowPath);
        }
      }
    });

    // Merge pairs
    Object.entries(toMerge).forEach(([basePath, variants]) => {
      const highModel = models[variants.high];
      const lowModel = models[variants.low];

      // Create merged model, prefer HIGH data but indicate both exist
      const merged = {
        ...highModel,
        name: highModel.name.replace(/HIGH/gi, "").replace(/LOW/gi, "").trim(),
        notes:
          (highModel.notes || "") +
          "\n\n[Variants: HIGH noise and LOW noise versions available]" +
          (lowModel.notes ? "\n\nLOW variant notes: " + lowModel.notes : ""),
        variants: {
          high: variants.high,
          low: variants.low,
        },
      };

      models[basePath] = merged;
    });

    // Remove individual HIGH/LOW entries
    toDelete.forEach((path) => delete models[path]);

    if (Object.keys(toMerge).length > 0) {
      console.log(
        `✅ Merged ${Object.keys(toMerge).length} HIGH/LOW variant pairs`
      );
    }
  }

  processModels() {
    // Convert models object to array with keys
    this.filteredModels = Object.entries(this.modelData.models).map(
      ([path, model]) => ({
        path,
        ...model,
      })
    );

    // Sort by name
    this.filteredModels.sort((a, b) =>
      (a.name || "").localeCompare(b.name || "")
    );
  }

  applyFilters() {
    if (!this.modelData) return;

    const searchTerm = document
      .getElementById("searchInput")
      .value.toLowerCase();

    // NEW: Get selected types (array of checked values)
    const selectedTypes = Array.from(
      document.querySelectorAll("#typeCheckboxes input:checked")
    ).map((cb) => cb.value);

    // NEW: Get selected base models (array of checked values)
    const selectedBases = Array.from(
      document.querySelectorAll("#baseCheckboxes input:checked")
    ).map((cb) => cb.value);

    const favoritesOnly = document.getElementById("favoritesFilter").checked;
    const hasImagesOnly = document.getElementById("hasImagesFilter").checked;

    this.filteredModels = Object.entries(this.modelData.models)
      .map(([path, model]) => ({ path, ...model }))
      .filter((model) => {
        // Search filter
        if (
          searchTerm &&
          !model.name.toLowerCase().includes(searchTerm) &&
          !model.tags?.some((tag) => tag.toLowerCase().includes(searchTerm))
        ) {
          return false;
        }

        // NEW: Type filter (if any types are selected, model must match one)
        if (
          selectedTypes.length > 0 &&
          !selectedTypes.includes(model.modelType)
        ) {
          return false;
        }

        // NEW: Base model filter (if any bases are selected, model must match one)
        if (
          selectedBases.length > 0 &&
          !selectedBases.includes(model.baseModel)
        ) {
          return false;
        }

        // Favorites filter
        if (favoritesOnly && !model.favorite) {
          return false;
        }

        // Has images filter
        if (
          hasImagesOnly &&
          (!model.exampleImages || model.exampleImages.length === 0)
        ) {
          return false;
        }

        return true;
      })
      .sort((a, b) => (a.name || "").localeCompare(b.name || ""));

    this.renderModelGrid();
    this.updateModelCount();
  }

  renderModelGrid() {
    const grid = document.getElementById("modelGrid");
    grid.innerHTML = "";

    if (this.filteredModels.length === 0) {
      grid.innerHTML = `
                <div class="welcome-screen">
                    <h2>No models found</h2>
                    <p>Try adjusting your filters</p>
                </div>
            `;
      return;
    }

    let visibleCount = 0;
    this.filteredModels.forEach((model) => {
      const card = this.createModelCard(model);
      if (card) {
        // Only add if card is not null (rating filter)
        grid.appendChild(card);
        visibleCount++;
      }
    });

    // If content rating filtered everything out
    if (visibleCount === 0) {
      grid.innerHTML = `
                <div class="welcome-screen">
                    <h2>No models available at this rating</h2>
                    <p>Try changing the content rating filter (🟢 PG → 🟡 R → 🔴 X)</p>
                </div>
            `;
    }
  }

  createModelCard(model) {
    //console.log("\n🎴 === createModelCard CALLED ===");
    //console.log("Model:", model.name);

    const isMissing = model._status === "missing";
    const missingBadge = isMissing
      ? '<div class="missing-badge">⚠️ MISSING</div>'
      : "";

    // Check if model should be shown based on content rating
    if (!this.canShowModel(model)) {
      //console.log("  ❌ Model hidden by canShowModel()");
      return null;
    }
    //console.log("  ✅ Model passed canShowModel()");

    const card = document.createElement("div");
    card.className = "model-card";
    card.dataset.modelPath = model.path;

    if (this.selectedModel?.path === model.path) {
      card.classList.add("selected");
    }

    // Get appropriate media for current rating
    //console.log("  Calling getAppropriateMedia()...");
    const appropriateMedia = this.getAppropriateMedia(model);

    let mediaHtml;

    if (appropriateMedia) {
      mediaHtml = this.renderMediaElement(appropriateMedia, model.name);
    } else {
      const icon = this.getModelTypeIcon(model.modelType);
      mediaHtml = `<div class="model-placeholder">${icon}</div>`;
    }

    // Add drop indicator for drag-drop
    const dropIndicator = `<div class="drop-indicator">📁</div>`;
    //${missingBadge}
    //${imageHtml}
    card.innerHTML = `
            
            ${dropIndicator}
            ${missingBadge}
            ${mediaHtml}
            <div class="model-info">
                <div class="model-header">
                    <div class="model-name">${this.escapeHtml(
                      model.name || "Unnamed Model"
                    )}</div>
                    <div class="favorite-icon" onclick="event.stopPropagation(); app.toggleFavorite('${this.escapeAttribute(
                      model.path
                    )}')">
                        ${model.favorite ? "⭐" : "☆"}
                    </div>
                </div>
                <div class="model-meta">
                    <div class="model-type">${
                      model.modelType || "Unknown"
                    }</div>
                    ${
                      model.baseModel
                        ? `<div class="model-base">${model.baseModel}</div>`
                        : ""
                    }
                </div>
            </div>
        `;

    card.addEventListener("click", () => {
      this.selectModel(model);
    });

    return card;
  }

  selectModel(model) {
    this.selectedModel = model;
    this.renderModelGrid(); // Re-render to update selection
    this.renderDetails(model);
  }

  renderDetails(model) {
    const sidebar = document.getElementById("detailsSidebar");

    sidebar.innerHTML = `
            <div class="details-content">
                <div class="details-header">
                    <div class="details-title">${this.escapeHtml(
                      model.name || "Unnamed Model"
                    )}</div>
                    <div class="details-actions">
                        <button class="btn btn-primary" onclick="app.openEditModal()">✏️ Edit</button>
                        ${
                          model.civitaiUrl
                            ? `<a href="${model.civitaiUrl}" target="_blank" class="btn btn-secondary">🌐 CivitAI</a>`
                            : ""
                        }
                        ${
                          model.huggingFaceUrl
                            ? `<a href="${model.huggingFaceUrl}" target="_blank" class="btn btn-secondary">🤗 HuggingFace</a>`
                            : ""
                        }
                        ${
                          model.githubUrl
                            ? `<a href="${model.githubUrl}" target="_blank" class="btn btn-secondary">🐙 GitHub</a>`
                            : ""
                        }
                        ${
                          model.otherUrl
                            ? `<a href="${model.otherUrl}" target="_blank" class="btn btn-secondary">🔗 Link</a>`
                            : ""
                        }
                    </div>
                </div>

                <!-- Basic Info -->
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">📋 Info</div>
                    </div>
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">Type</span>
                            <span class="info-value">${
                              model.modelType || "Unknown"
                            }</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">File Type</span>
                            <span class="info-value">${
                              model.fileType || "Unknown"
                            }</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Base Model</span>
                            <span class="info-value">${
                              model.baseModel || "Not specified"
                            }</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">NSFW</span>
                            <span class="info-value">${
                              model.nsfw ? "🔞 Yes" : "✅ No"
                            }</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Path</span>
                            <span class="info-value" style="font-size: 11px; word-break: break-all;">${
                              model.path
                            }</span>
                        </div>
                    </div>
                </div>

                <!-- Tags -->
                ${
                  model.tags && model.tags.length > 0
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">🏷️ Tags</div>
                    </div>
                    <div class="tag-list">
                        ${model.tags
                          .map(
                            (tag) =>
                              `<span class="tag">${this.escapeHtml(tag)}</span>`
                          )
                          .join("")}
                    </div>
                </div>
                `
                    : ""
                }

                <!-- Trigger Words -->
                ${
                  model.triggerWords &&
                  model.triggerWords.length > 0 &&
                  model.triggerWords[0] !== ""
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">✨ Trigger Words</div>
                        <button class="btn-copy" onclick="app.copyTriggerWords()">📋 Copy All</button>
                    </div>
                    <div>
                        ${model.triggerWords
                          .map(
                            (word) =>
                              `<span class="trigger-word">${this.escapeHtml(
                                word
                              )}</span>`
                          )
                          .join("")}
                    </div>
                </div>
                `
                    : ""
                }

                <!-- Recommended Settings -->
                ${this.renderRecommendedSettings(model)}

                <!-- Notes -->
                ${
                  model.notes
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">📝 Notes</div>
                    </div>
                    <div class="notes-content">${this.escapeHtml(
                      model.notes
                    )}</div>
                </div>
                `
                    : ""
                }

                <!-- Example Prompts -->
                ${
                  model.examplePrompts && model.examplePrompts.length > 0
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">💡 Example Prompts</div>
                    </div>
                    ${model.examplePrompts
                      .map(
                        (prompt, idx) => `
                        <div class="example-prompt">
                            <div class="prompt-title">${this.escapeHtml(
                              prompt.title
                            )}</div>
                            <div class="prompt-text">${this.escapeHtml(
                              prompt.prompt
                            )}</div>
                            <button class="btn-copy prompt-copy" onclick="app.copyPrompt(${idx})">📋</button>
                        </div>
                    `
                      )
                      .join("")}
                </div>
                `
                    : ""
                }

                <!-- Example Images -->
                ${
                  model.exampleImages && model.exampleImages.length > 0
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">🖼️ Example Images</div>
                    </div>
                    <div class="image-gallery">
                        ${model.exampleImages
                          .filter((img) => {
                            const imgRating =
                              img.rating || (model.nsfw ? "x" : "pg");
                            return (
                              this.getRatingValue(imgRating) <=
                              this.getRatingValue(this.contentRating)
                            );
                          })
                          .map(
                            (img) => `
                            <div class="gallery-image" onclick="app.openLightbox('${
                              img.filename
                            }', '${this.escapeAttribute(
                              img.caption || model.name
                            )}', '${this.escapeAttribute(model.path)}')">
                              ${this.renderMediaElement(
                                img,
                                img.caption || model.name
                              )}
                            </div>
                        `
                          )
                          .join("")}
                    </div>
                </div>
                `
                    : ""
                }
            </div>
        `;

    const missingWarning =
      model._status === "missing"
        ? `
  <div class="missing-warning">
    <div class="warning-header">Model File Not Found</div>
    <p>This model was in your database but wasn't found in the last filesystem scan.</p>
    <p><strong>Last known location:</strong></p>
    <div class="last-seen-path">${this.escapeHtml(
      model._lastSeenPath || "Unknown"
    )}</div>
    <p>The model may have been moved, renamed, or deleted.</p>
    <button class="btn btn-danger" onclick="app.deleteMissingModel('${this.escapeAttribute(
      model.path
    )}')">
      🗑️ Remove from Database
    </button>
  </div>
`
        : "";

    // Add ${missingWarning} at the start of the details-content
  }

  async deleteMissingModel(path) {
    if (
      !confirm(
        "Remove this missing model from the database?\n\nThis will delete all associated data including notes, tags, and images. This cannot be undone."
      )
    ) {
      return;
    }

    try {
      console.log("🗑️ Deleting missing model:", path);

      // Remove from local data
      delete this.modelData.models[path];

      // Save to server
      const response = await fetch("/api/models", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.modelData),
      });

      if (!response.ok) {
        throw new Error("Failed to save database");
      }

      this.showToast("✅ Missing model removed");

      // Reload and reset view
      await this.loadFromServer();
      this.selectedModel = null;
      document.getElementById("detailsSidebar").innerHTML =
        '<div class="no-selection"><p>Select a model to view details</p></div>';

      console.log("✅ Missing model deleted successfully");
    } catch (error) {
      console.error("Failed to delete missing model:", error);
      this.showToast("❌ Failed to delete: " + error.message);
    }
  }

  renderRecommendedSettings(model) {
    if (
      !model.recommendedSettings ||
      Object.keys(model.recommendedSettings).length === 0
    ) {
      return "";
    }

    // Define which fields are relevant for each model type
    const fieldsByType = {
      checkpoint: ["resolution", "sampler", "steps", "cfg", "clipSkip"],
      lora: ["weight", "resolution", "steps", "cfg"],
      controlnet: ["preprocessor", "weight", "guidanceStart", "guidanceEnd"],
      upscaler: ["scale", "tileSize"],
      vae: [], // VAE has no specific recommended settings typically
      embedding: ["weight"],
      hypernetwork: ["weight"],
    };

    const relevantFields = fieldsByType[model.modelType] || [];
    if (relevantFields.length === 0) return "";

    const settingsHtml = Object.entries(model.recommendedSettings)
      .filter(([key]) => relevantFields.includes(key))
      .map(
        ([key, value]) => `
      <div class="info-item">
        <span class="info-label">${this.formatKey(key)}</span>
        <span class="info-value">${this.escapeHtml(value)}</span>
      </div>
    `
      )
      .join("");

    if (!settingsHtml) return "";

    return `
    <div class="section">
      <div class="section-header">
        <div class="section-title">⚙️ Recommended Settings</div>
      </div>
      <div class="info-grid">
        ${settingsHtml}
      </div>
    </div>
  `;
  }

  openEditModal() {
    if (!this.selectedModel) return;

    const modal = document.getElementById("editModal");
    const modalBody = document.getElementById("editModalBody");

    const model = this.selectedModel;

    modalBody.innerHTML = `
            <form id="editForm">
                <div class="form-group">
                    <label class="form-label">Model Name</label>
                    <input type="text" class="form-input" name="name" value="${this.escapeHtml(
                      model.name || ""
                    )}" required>
                </div>

                <div class="form-group">
                    <label class="form-label">Model Type</label>
                    <select class="form-select" name="modelType">
                        <option value="checkpoint" ${
                          model.modelType === "checkpoint" ? "selected" : ""
                        }>Checkpoint</option>
                        <option value="lora" ${
                          model.modelType === "lora" ? "selected" : ""
                        }>LoRA</option>
                        <option value="controlnet" ${
                          model.modelType === "controlnet" ? "selected" : ""
                        }>ControlNet</option>
                        <option value="upscaler" ${
                          model.modelType === "upscaler" ? "selected" : ""
                        }>Upscaler</option>
                        <option value="vae" ${
                          model.modelType === "vae" ? "selected" : ""
                        }>VAE</option>
                        <option value="embedding" ${
                          model.modelType === "embedding" ? "selected" : ""
                        }>Embedding</option>
                        <option value="hypernetwork" ${
                          model.modelType === "hypernetwork" ? "selected" : ""
                        }>Hypernetwork</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">File Type</label>
                    <select class="form-select" name="fileType">
                        <option value="safetensors" ${
                          model.fileType === "safetensors" ? "selected" : ""
                        }>Safetensors</option>
                        <option value="ckpt" ${
                          model.fileType === "ckpt" ? "selected" : ""
                        }>CKPT</option>
                        <option value="pt" ${
                          model.fileType === "pt" ? "selected" : ""
                        }>PT</option>
                        <option value="pth" ${
                          model.fileType === "pth" ? "selected" : ""
                        }>PTH</option>
                        <option value="bin" ${
                          model.fileType === "bin" ? "selected" : ""
                        }>BIN</option>
                        <option value="gguf" ${
                          model.fileType === "gguf" ? "selected" : ""
                        }>GGUF</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">Base Model</label>
                    <input type="text" class="form-input" name="baseModel" value="${this.escapeHtml(
                      model.baseModel || ""
                    )}" placeholder="e.g., SD1.5, SDXL, Flux">
                </div>

                <div class="form-group">
                    <label class="form-checkbox">
                        <input type="checkbox" name="nsfw" ${
                          model.nsfw ? "checked" : ""
                        }>
                        <span>NSFW Content</span>
                    </label>
                </div>

                <div class="form-group">
                    <label class="form-checkbox">
                        <input type="checkbox" name="favorite" ${
                          model.favorite ? "checked" : ""
                        }>
                        <span>⭐ Favorite</span>
                    </label>
                </div>

                <div class="form-group">
                    <label class="form-label">Tags (comma-separated)</label>
                    <input type="text" class="form-input" name="tags" value="${(
                      model.tags || []
                    ).join(", ")}" placeholder="realistic, portrait, anime">
                </div>

                <div class="form-group">
                    <label class="form-label">Trigger Words (comma-separated)</label>
                    <input type="text" class="form-input" name="triggerWords" value="${(
                      model.triggerWords || []
                    )
                      .filter((w) => w !== "")
                      .join(", ")}" placeholder="detailed, intricate">
                </div>

                <div class="form-group">
                    <label class="form-label">CivitAI URL</label>
                    <input type="url" class="form-input" name="civitaiUrl" value="${
                      model.civitaiUrl || ""
                    }" placeholder="https://civitai.com/models/...">
                </div>
                <div class="form-group">
                    <label class="form-label">HuggingFace URL</label>
                    <input type="url" class="form-input" name="huggingFaceUrl" value="${
                      model.huggingFaceUrl || ""
                    }" placeholder="https://huggingface.co/...">
                </div>

                <div class="form-group">
                    <label class="form-label">GitHub URL</label>
                    <input type="url" class="form-input" name="githubUrl" value="${
                      model.githubUrl || ""
                    }" placeholder="https://github.com/...">
                </div>

                <div class="form-group">
                    <label class="form-label">Other URL</label>
                    <input type="url" class="form-input" name="otherUrl" value="${
                      model.otherUrl || ""
                    }" placeholder="https://...">
                </div>

                <div class="form-group">
                    <label class="form-label">Notes</label>
                    <textarea class="form-textarea" name="notes" placeholder="Add your notes here...">${this.escapeHtml(
                      model.notes || ""
                    )}</textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">Recommended Settings</label>
                    ${this.renderSettingsInputs(model)}
                </div>

                <div class="form-group">
                    <label class="form-label">Example Prompts</label>
                    <div id="promptsList">
                        ${(model.examplePrompts || [])
                          .map(
                            (prompt, idx) => `
                            <div class="prompt-editor" data-idx="${idx}">
                                <input type="text" class="form-input" placeholder="Prompt title" value="${this.escapeHtml(
                                  prompt.title
                                )}" name="promptTitle_${idx}">
                                <textarea class="form-textarea" placeholder="Prompt text" name="promptText_${idx}" style="margin-top: 8px; min-height: 60px;">${this.escapeHtml(
                              prompt.prompt
                            )}</textarea>
                                <button type="button" class="btn-remove" onclick="app.removePrompt(${idx})">Remove</button>
                            </div>
                        `
                          )
                          .join("")}
                    </div>
                    <button type="button" class="btn-add" onclick="app.addPrompt()">+ Add Prompt</button>
                </div>

                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="app.closeEditModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">💾 Save Changes</button>
                </div>
            </form>
        `;

    // Form submit handler
    document.getElementById("editForm").addEventListener("submit", (e) => {
      e.preventDefault();
      this.saveModelEdits();
    });

    modal.style.display = "flex";
  }

  saveModelEdits() {
    const form = document.getElementById("editForm");
    const formData = new FormData(form);

    // Get the model from modelData
    const model = this.modelData.models[this.selectedModel.path];

    // Update basic fields
    model.name = formData.get("name");
    model.modelType = formData.get("modelType");
    model.fileType = formData.get("fileType");
    model.baseModel = formData.get("baseModel");
    model.nsfw = formData.get("nsfw") === "on";
    model.favorite = formData.get("favorite") === "on";
    model.civitaiUrl = formData.get("civitaiUrl");
    model.huggingFaceUrl = formData.get("huggingFaceUrl");
    model.githubUrl = formData.get("githubUrl");
    model.otherUrl = formData.get("otherUrl");
    model.notes = formData.get("notes");

    // Parse tags
    const tagsInput = formData.get("tags");
    model.tags = tagsInput
      ? tagsInput
          .split(",")
          .map((t) => t.trim())
          .filter((t) => t)
      : [];

    // Parse trigger words
    const triggerWordsInput = formData.get("triggerWords");
    model.triggerWords = triggerWordsInput
      ? triggerWordsInput
          .split(",")
          .map((t) => t.trim())
          .filter((t) => t)
      : [];

    // Update recommended settings (only save non-empty values)
    const fieldsByType = {
      checkpoint: ["resolution", "sampler", "steps", "cfg", "clipSkip"],
      lora: ["weight", "resolution", "steps", "cfg"],
      controlnet: ["preprocessor", "weight", "guidanceStart", "guidanceEnd"],
      upscaler: ["scale", "tileSize"],
      vae: [],
      embedding: ["weight"],
      hypernetwork: ["weight"],
    };

    const relevantFields =
      fieldsByType[model.modelType] || fieldsByType.checkpoint;
    model.recommendedSettings = {};

    relevantFields.forEach((field) => {
      const value = formData.get(field);
      if (value && value.trim()) {
        model.recommendedSettings[field] = value.trim();
      }
    });

    // Update example prompts
    const promptEditors = document.querySelectorAll(".prompt-editor");
    model.examplePrompts = Array.from(promptEditors)
      .map((editor) => {
        const idx = editor.dataset.idx;
        return {
          title: formData.get(`promptTitle_${idx}`) || "",
          prompt: formData.get(`promptText_${idx}`) || "",
        };
      })
      .filter((p) => p.title || p.prompt);

    // Update selectedModel reference
    this.selectedModel = { path: this.selectedModel.path, ...model };

    // Mark as dirty and save immediately
    this.isDirty = true;
    this.autoSave(); // Save immediately on edit

    // Re-render
    this.applyFilters();
    this.renderDetails(this.selectedModel);
    this.closeEditModal();

    console.log("✅ Model updated:", model.name);
  }

  addPrompt() {
    const promptsList = document.getElementById("promptsList");
    const idx = promptsList.children.length;

    const promptEditor = document.createElement("div");
    promptEditor.className = "prompt-editor";
    promptEditor.dataset.idx = idx;
    promptEditor.innerHTML = `
            <input type="text" class="form-input" placeholder="Prompt title" name="promptTitle_${idx}">
            <textarea class="form-textarea" placeholder="Prompt text" name="promptText_${idx}" style="margin-top: 8px; min-height: 60px;"></textarea>
            <button type="button" class="btn-remove" onclick="app.removePrompt(${idx})">Remove</button>
        `;

    promptsList.appendChild(promptEditor);
  }

  removePrompt(idx) {
    const promptEditor = document.querySelector(
      `.prompt-editor[data-idx="${idx}"]`
    );
    if (promptEditor) {
      promptEditor.remove();
    }
  }

  closeEditModal() {
    document.getElementById("editModal").style.display = "none";
  }

  async toggleFavorite(path) {
    try {
      const response = await fetch(
        `/api/models/${encodeURIComponent(path)}/favorite`,
        {
          method: "POST",
        }
      );

      if (response.ok) {
        const result = await response.json();
        const model = this.modelData.models[path];
        model.favorite = result.favorite;
        this.applyFilters();

        if (this.selectedModel?.path === path) {
          this.selectedModel.favorite = model.favorite;
          this.renderDetails(this.selectedModel);
        }
      }
    } catch (error) {
      console.error("Failed to toggle favorite:", error);
      this.showToast("❌ Failed to update favorite");
    }
  }

  openLightbox(imagePath, caption, modelPath) {
    const lightbox = document.getElementById("imageLightbox");
    const lightboxContent = document.getElementById("lightboxContent");
    const lightboxCaption = document.getElementById("lightboxCaption");
    const lightboxControls = document.getElementById("lightboxControls");

    // Find the media item and model
    let model = this.selectedModel;
    let actualModelPath = this.selectedModel?.path;
    if (modelPath) {
      model = this.modelData.models[modelPath];
      actualModelPath = modelPath;
    }

    if (!model || !model.exampleImages) {
      console.error("Model or images not found");
      return;
    }

    const mediaItem = model.exampleImages.find(
      (img) => img.filename === imagePath
    );

    if (!mediaItem) {
      console.error("Media item not found:", imagePath);
      return;
    }

    // Render media (image or video)
    const ext = imagePath.toLowerCase();
    const isVideo = ext.endsWith(".mp4") || ext.endsWith(".webm");

    if (isVideo) {
      lightboxContent.innerHTML = `
      <video id="lightboxMedia" autoplay loop muted controls style="max-width: 90%; max-height: 90vh; border-radius: 8px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);">
        <source src="images/${imagePath}" type="video/${ext.split(".").pop()}">
      </video>
    `;
    } else {
      lightboxContent.innerHTML = `
      <img id="lightboxMedia" src="images/${imagePath}" alt="${this.escapeHtml(
        caption || ""
      )}" style="max-width: 90%; max-height: 90vh; border-radius: 8px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);">
    `;
    }

    lightboxCaption.textContent = caption || "";

    // Add rating controls
    const currentRating = mediaItem.rating || (model.nsfw ? "x" : "pg");
    lightboxControls.innerHTML = `
    <div class="lightbox-rating-controls">
      <label style="color: #6272a4; font-size: 14px; margin-right: 12px;">Rating:</label>
      <select class="lightbox-rating-select" id="lightboxRatingSelect">
        <option value="pg" ${
          currentRating === "pg" ? "selected" : ""
        }>🟢 PG</option>
        <option value="r" ${
          currentRating === "r" ? "selected" : ""
        }>🟡 R</option>
        <option value="x" ${
          currentRating === "x" ? "selected" : ""
        }>🔴 X</option>
      </select>
      <button class="btn-lightbox-save" onclick="app.saveLightboxRating('${this.escapeAttribute(
        imagePath
      )}', '${this.escapeAttribute(actualModelPath)}')">💾 Save</button>
      <button class="btn-lightbox-delete" onclick="app.deleteLightboxMedia('${this.escapeAttribute(
        imagePath
      )}', '${this.escapeAttribute(actualModelPath)}')">🗑️ Delete</button>
          </div>
        `;

    lightbox.style.display = "flex";
  }

  closeLightbox() {
    const lightbox = document.getElementById("imageLightbox");
    lightbox.style.display = "none";
  }

  async saveLightboxRating(imagePath, modelPath) {
    try {
      const select = document.getElementById("lightboxRatingSelect");
      const newRating = select.value;

      const response = await fetch(
        `/api/models/${encodeURIComponent(modelPath)}/update-media-rating`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: imagePath,
            rating: newRating,
          }),
        }
      );

      if (response.ok) {
        this.showToast("✅ Rating updated!");
        // Reload data to reflect changes
        await this.loadFromServer();

        // Re-select the model if it was selected
        if (this.selectedModel?.path === modelPath) {
          this.selectedModel = this.modelData.models[modelPath];
          this.renderDetails(this.selectedModel);
        }
      } else {
        this.showToast("❌ Failed to update rating");
      }
    } catch (error) {
      console.error("Failed to update rating:", error);
      this.showToast("❌ Failed to update rating");
    }
  }

  async deleteLightboxMedia(imagePath, modelPath) {
    if (!confirm("Are you sure you want to delete this media?")) {
      return;
    }

    try {
      const response = await fetch(
        `/api/models/${encodeURIComponent(modelPath)}/delete-media`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: imagePath,
          }),
        }
      );

      if (response.ok) {
        this.showToast("✅ Media deleted!");
        this.closeLightbox();

        // Reload data to reflect changes
        await this.loadFromServer();

        // Re-select the model if it was selected
        if (this.selectedModel?.path === modelPath) {
          this.selectedModel = this.modelData.models[modelPath];
          this.renderDetails(this.selectedModel);
        }
      } else {
        this.showToast("❌ Failed to delete media");
      }
    } catch (error) {
      console.error("Failed to delete media:", error);
      this.showToast("❌ Failed to delete media");
    }
  }

  toggleNsfwFilter() {
    this.nsfwFilterEnabled = !this.nsfwFilterEnabled;
    const icon = document.getElementById("nsfwIcon");
    icon.textContent = this.nsfwFilterEnabled ? "🔒" : "🔓";

    if (this.modelData) {
      this.renderModelGrid();
      if (this.selectedModel) {
        this.renderDetails(this.selectedModel);
      }
    }
  }

  copyTriggerWords() {
    if (!this.selectedModel?.triggerWords) return;

    const text = this.selectedModel.triggerWords
      .filter((w) => w !== "")
      .join(", ");
    navigator.clipboard.writeText(text).then(() => {
      this.showToast("✅ Trigger words copied!");
    });
  }

  copyPrompt(idx) {
    if (!this.selectedModel?.examplePrompts?.[idx]) return;

    const prompt = this.selectedModel.examplePrompts[idx].prompt;
    navigator.clipboard.writeText(prompt).then(() => {
      this.showToast("✅ Prompt copied!");
    });
  }

  showToast(message) {
    // Simple toast notification
    const toast = document.createElement("div");
    toast.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: rgba(80, 250, 123, 0.9);
            color: #282a36;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            z-index: 10000;
            animation: fadeIn 0.3s ease;
        `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = "fadeOut 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }

  exportJson() {
    if (!this.modelData) return;

    const jsonString = JSON.stringify(this.modelData, null, 2);
    const blob = new Blob([jsonString], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "modeldb.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.isDirty = false;

    // Update button to show no changes
    const exportBtn = document.getElementById("exportJsonBtn");
    exportBtn.textContent = "💾 Export JSON";
    exportBtn.title = "Export database to file";

    this.showToast("✅ JSON exported successfully!");
    console.log("✅ Exported modeldb.json");
  }

  async autoSave() {
    if (!this.modelData || !this.serverMode) return;

    try {
      const response = await fetch("/api/models", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(this.modelData),
      });

      if (response.ok) {
        console.log("💾 Auto-saved to server");
        this.isDirty = false;

        // Update button
        const exportBtn = document.getElementById("exportJsonBtn");
        exportBtn.textContent = "💾 Export JSON";
        exportBtn.title = "Export database to file";
      } else {
        console.warn("Auto-save failed:", response.statusText);
      }
    } catch (error) {
      console.warn("Auto-save failed:", error);
      this.showToast("⚠️ Auto-save failed - check server connection");
    }
  }

  applyContentRating() {
    console.log("\n🔄 === applyContentRating CALLED ===");
    console.log("New rating:", this.contentRating);

    if (this.modelData) {
      console.log("Calling processModels()...");
      this.processModels();

      console.log("Calling applyFilters()...");
      this.applyFilters();

      if (this.selectedModel) {
        console.log("Re-rendering details for:", this.selectedModel.name);
        this.renderDetails(this.selectedModel);
      }
    }
    console.log("=== applyContentRating DONE ===\n");
  }

  openImportModal() {
    const modal = document.getElementById("importModal");
    const uploadStep = document.getElementById("uploadStep");
    const previewStep = document.getElementById("previewStep");
    const confirmBtn = document.getElementById("confirmMergeBtn");

    // Reset to upload step
    uploadStep.style.display = "block";
    previewStep.style.display = "none";
    confirmBtn.style.display = "none";

    // Clear any pending merge
    this.pendingMerge = null;

    modal.style.display = "flex";

    // Setup drag & drop (only once)
    if (!this.importDragDropSetup) {
      this.setupImportDragDrop();
      this.importDragDropSetup = true;
    }
  }

  closeImportModal() {
    document.getElementById("importModal").style.display = "none";
    this.pendingMerge = null;

    // Clear file input
    const fileInput = document.getElementById("importFileInput");
    if (fileInput) fileInput.value = "";
  }

  setupImportDragDrop() {
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("importFileInput");

    // Prevent default drag behaviors
    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    // Visual feedback
    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.add("drag-active");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.remove("drag-active");
      });
    });

    // Handle drop
    dropZone.addEventListener("drop", (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        this.handleImportFile(files[0]);
      }
    });

    // Handle file input
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        this.handleImportFile(e.target.files[0]);
      }
    });

    // Click to browse
    dropZone.addEventListener("click", (e) => {
      if (e.target === dropZone || e.target.closest(".drop-zone-content")) {
        fileInput.click();
      }
    });
  }

  async handleImportFile(file) {
    try {
      console.log("📥 Importing file:", file.name);

      if (!file.name.endsWith(".json")) {
        this.showToast("❌ Please upload a JSON file");
        return;
      }

      // Show loading state
      const dropZone = document.getElementById("dropZone");
      dropZone.classList.add("loading");

      // Read file
      const fileContent = await file.text();
      const newDb = JSON.parse(fileContent);

      // Remove loading state
      dropZone.classList.remove("loading");

      // Validate structure
      if (!newDb.models || typeof newDb.models !== "object") {
        this.showToast("❌ Invalid database format - missing models object");
        return;
      }

      console.log(
        "✅ Loaded new database:",
        Object.keys(newDb.models).length,
        "models"
      );

      // Perform merge analysis
      const mergeResult = this.analyzeMerge(this.modelData, newDb);

      console.log("📊 Merge analysis complete:", mergeResult.stats);

      // Store for later
      this.pendingMerge = {
        newDb: newDb,
        analysis: mergeResult,
      };

      // Show preview
      this.showMergePreview(mergeResult);
    } catch (error) {
      console.error("Failed to import file:", error);
      this.showToast("❌ Failed to read file: " + error.message);

      const dropZone = document.getElementById("dropZone");
      dropZone.classList.remove("loading");
    }
  }

  analyzeMerge(oldDb, newDb) {
    console.log("🔍 Analyzing merge...");

    const result = {
      matched: [],
      new: [],
      missing: [],
      stats: { matched: 0, new: 0, missing: 0 },
    };

    // Build hash index of old database
    const oldByHash = new Map();
    Object.entries(oldDb.models || {}).forEach(([path, model]) => {
      if (model.fileHash) {
        oldByHash.set(model.fileHash, { path, model });
      } else {
        console.warn("⚠️ Model without hash:", path);
      }
    });

    console.log("📚 Old database:", oldByHash.size, "models with hashes");

    // Process new database
    Object.entries(newDb.models || {}).forEach(([newPath, newModel]) => {
      const hash = newModel.fileHash;

      if (!hash) {
        console.warn("⚠️ New model without hash:", newPath);
        return;
      }

      if (oldByHash.has(hash)) {
        // MATCHED: Model exists in both databases
        const { path: oldPath, model: oldModel } = oldByHash.get(hash);
        result.matched.push({
          hash,
          oldPath,
          newPath,
          name: newModel.name || oldModel.name || "Unnamed",
          pathChanged: oldPath !== newPath,
        });
        result.stats.matched++;
        oldByHash.delete(hash); // Mark as processed
      } else {
        // NEW: Model only in new database
        result.new.push({
          hash,
          path: newPath,
          name: newModel.name || "Unnamed",
        });
        result.stats.new++;
      }
    });

    // Remaining in oldByHash are MISSING
    oldByHash.forEach(({ path, model }) => {
      result.missing.push({
        hash: model.fileHash,
        path,
        name: model.name || "Unnamed",
      });
      result.stats.missing++;
    });

    console.log("✅ Analysis complete:", result.stats);

    return result;
  }

  showMergePreview(analysis) {
    const uploadStep = document.getElementById("uploadStep");
    const previewStep = document.getElementById("previewStep");
    const confirmBtn = document.getElementById("confirmMergeBtn");

    // Switch to preview step
    uploadStep.style.display = "none";
    previewStep.style.display = "block";
    confirmBtn.style.display = "block";

    // Update stats
    document.getElementById("matchedCount").textContent =
      analysis.stats.matched;
    document.getElementById("newCount").textContent = analysis.stats.new;
    document.getElementById("missingCount").textContent =
      analysis.stats.missing;

    document.getElementById("matchedCountDetail").textContent =
      analysis.stats.matched;
    document.getElementById("newCountDetail").textContent = analysis.stats.new;
    document.getElementById("missingCountDetail").textContent =
      analysis.stats.missing;

    // Populate detail lists
    this.populateMergeList("matchedList", analysis.matched, "matched");
    this.populateMergeList("newList", analysis.new, "new");
    this.populateMergeList("missingList", analysis.missing, "missing");

    // Setup confirm button
    confirmBtn.onclick = () => this.executeMerge();
  }

  populateMergeList(elementId, items, type) {
    const list = document.getElementById(elementId);

    if (items.length === 0) {
      list.innerHTML = '<div class="merge-detail-item empty">No items</div>';
      return;
    }

    list.innerHTML = items
      .map((item) => {
        let html = `<div class="merge-detail-item ${type}">`;
        html += `<div class="item-name">${this.escapeHtml(item.name)}</div>`;

        if (type === "matched" && item.pathChanged) {
          html += `<div class="item-path">${this.escapeHtml(
            item.newPath
          )}</div>`;
          html += `<div class="item-note">📁 Path changed from: ${this.escapeHtml(
            item.oldPath
          )}</div>`;
        } else {
          html += `<div class="item-path">${this.escapeHtml(item.path)}</div>`;
        }

        html += "</div>";
        return html;
      })
      .join("");
  }

  async executeMerge() {
    if (!this.pendingMerge) {
      console.error("No pending merge");
      return;
    }

    try {
      console.log("🔄 Executing merge...");
      this.showToast("⏳ Merging databases...");

      const { newDb, analysis } = this.pendingMerge;
      const mergedDb = this.performMerge(this.modelData, newDb, analysis);

      console.log("✅ Merge complete, saving...");

      // Save merged database (will auto-backup)
      const response = await fetch("/api/models", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mergedDb),
      });

      if (!response.ok) {
        throw new Error("Failed to save merged database");
      }

      console.log("💾 Merge saved successfully");

      // Reload data from server
      await this.loadFromServer();

      this.showToast(
        `✅ Merge complete! ${analysis.stats.matched} matched, ${analysis.stats.new} new, ${analysis.stats.missing} missing`
      );
      this.closeImportModal();
    } catch (error) {
      console.error("Merge failed:", error);
      this.showToast("❌ Merge failed: " + error.message);
    }
  }

  performMerge(oldDb, newDb, analysis) {
    console.log("🔀 Performing merge...");

    const merged = {
      version: newDb.version || oldDb.version || "1.0.0",
      models: {},
    };

    // Build hash maps for quick lookup
    const oldByHash = new Map();
    Object.entries(oldDb.models || {}).forEach(([path, model]) => {
      if (model.fileHash) {
        oldByHash.set(model.fileHash, model);
      }
    });

    // Process all models from new database
    Object.entries(newDb.models).forEach(([newPath, newModel]) => {
      const hash = newModel.fileHash;

      if (!hash) {
        console.warn("⚠️ Skipping model without hash:", newPath);
        return;
      }

      if (oldByHash.has(hash)) {
        // MATCHED: Merge old and new data
        const oldModel = oldByHash.get(hash);
        merged.models[newPath] = this.mergeModelData(oldModel, newModel);
        console.log("✅ Merged:", newPath);
      } else {
        // NEW: Just add it
        merged.models[newPath] = newModel;
        console.log("➕ Added new:", newPath);
      }
    });

    // Process missing models (mark but keep)
    analysis.missing.forEach((item) => {
      const oldModel = oldByHash.get(item.hash);
      if (oldModel) {
        const missingKey = `_missing/${item.path}`;
        merged.models[missingKey] = {
          ...oldModel,
          _status: "missing",
          _lastSeenPath: item.path,
        };
        console.log("⚠️ Marked as missing:", item.path);
      }
    });

    console.log(
      "✅ Merge complete:",
      Object.keys(merged.models).length,
      "total models"
    );

    return merged;
  }

  mergeModelData(oldModel, newModel) {
    // Start with new model (has current filesystem data)
    const merged = { ...newModel };

    // Fields to preserve from old model if they have user data
    const manualFields = [
      "favorite",
      "notes",
      "tags",
      "triggerWords",
      "civitaiUrl",
      "huggingFaceUrl",
      "githubUrl",
      "otherUrl",
      "recommendedSettings",
      "examplePrompts",
      "exampleImages",
      "nsfw",
    ];

    manualFields.forEach((field) => {
      const oldValue = oldModel[field];

      // Skip if old value doesn't exist
      if (oldValue === undefined || oldValue === null) {
        return;
      }

      // Check if it's a non-empty value worth preserving
      let shouldPreserve = false;

      if (Array.isArray(oldValue)) {
        shouldPreserve = oldValue.length > 0;
      } else if (typeof oldValue === "object") {
        shouldPreserve = Object.keys(oldValue).length > 0;
      } else if (typeof oldValue === "boolean") {
        shouldPreserve = true; // Always preserve boolean values
      } else if (typeof oldValue === "string") {
        shouldPreserve = oldValue.trim() !== "";
      } else {
        shouldPreserve = true;
      }

      if (shouldPreserve) {
        merged[field] = oldValue;
      }
    });

    return merged;
  }

  toggleVideoMode() {
    this.showVideos = !this.showVideos;
    const btn = document.getElementById("videoToggle");
    btn.innerHTML = this.showVideos ? "🎬 Videos" : "🖼️ Images";
    btn.title = this.showVideos
      ? "Showing videos (click for images only)"
      : "Showing images only (click to include videos)";

    // Re-render to apply changes
    if (this.modelData) {
      this.processModels();
      this.applyFilters();
      if (this.selectedModel) {
        this.renderDetails(this.selectedModel);
      }
    }
    console.log(`Video mode: ${this.showVideos ? "ON" : "OFF"}`);
  }

  getRatingValue(rating) {
    const values = { pg: 0, r: 1, x: 2 };
    return values[rating] || 0;
  }

  getModelMaxRating(model) {
    if (!model.exampleImages || model.exampleImages.length === 0) {
      return "pg";
    }

    const hasPgImage = model.exampleImages.some((img) => {
      const rating = img.rating || "pg";
      return rating === "pg";
    });
    const hasRImage = model.exampleImages.some((img) => img.rating === "r");
    const hasXImage = model.exampleImages.some((img) => img.rating === "x");

    if (hasPgImage) return "pg";
    if (hasRImage) return "r";
    if (hasXImage) return "x";
    return "pg";
  }

  canShowModel(model) {
    const currentRatingValue = this.getRatingValue(this.contentRating);

    // If model has no images
    if (!model.exampleImages || model.exampleImages.length === 0) {
      // NSFW models without images only show at X rating
      if (model.nsfw) {
        return currentRatingValue >= this.getRatingValue("x");
      }
      return true; // Non-NSFW models with no images always show
    }

    // Model has images - check if any are appropriate for current rating
    const hasAppropriateImage = model.exampleImages.some((img) => {
      // DEFAULT RATING: If image has no rating, use X for NSFW models, PG for others
      const imgRating = img.rating || (model.nsfw ? "x" : "pg");
      return this.getRatingValue(imgRating) <= currentRatingValue;
    });

    return hasAppropriateImage;
  }

  getAppropriateMedia(model) {
    //console.log("=== getAppropriateMedia CALLED ===");
    //console.log("Model name:", model.name);
    //console.log("Current content rating:", this.contentRating);
    //console.log("Show videos:", this.showVideos);

    if (!model.exampleImages || model.exampleImages.length === 0) {
      //console.log("  ❌ No images found");
      return null;
    }

    console.log("Total images:", model.exampleImages.length);
    model.exampleImages.forEach((img, i) => {
      console.log(
        `  Image ${i}:`,
        img.filename,
        "Rating:",
        img.rating || "NONE"
      );
    });

    const currentRatingValue = this.getRatingValue(this.contentRating);
    console.log("Current rating value:", currentRatingValue);

    // Filter by rating first
    let appropriateMedia = model.exampleImages.filter((item) => {
      const itemRating = item.rating || "pg";
      const passes = this.getRatingValue(itemRating) <= currentRatingValue;
      console.log(
        `  Check ${item.filename}: rating=${itemRating}, passes=${passes}`
      );
      return passes;
    });

    console.log("After rating filter:", appropriateMedia.length, "images");

    if (appropriateMedia.length === 0) {
      console.log("  ❌ No appropriate media found");
      return null;
    }

    // If videos disabled, filter out videos
    if (!this.showVideos) {
      const imagesOnly = appropriateMedia.filter((item) => {
        const ext = (item.filename || "").toLowerCase();
        const isVideo = ext.endsWith(".mp4") || ext.endsWith(".webm");
        console.log(`    ${item.filename} is video: ${isVideo}`);
        return !isVideo;
      });
      appropriateMedia = imagesOnly.length > 0 ? imagesOnly : appropriateMedia;
      console.log("After video filter:", appropriateMedia.length, "images");
    }

    // Sort by rating value (highest first)
    appropriateMedia.sort((a, b) => {
      const ratingA = a.rating || "pg";
      const ratingB = b.rating || "pg";
      const valA = this.getRatingValue(ratingA);
      const valB = this.getRatingValue(ratingB);
      console.log(`  Sort: ${a.filename}(${valA}) vs ${b.filename}(${valB})`);
      return valB - valA;
    });

    console.log(
      "✅ Selected media:",
      appropriateMedia[0]?.filename,
      "Rating:",
      appropriateMedia[0]?.rating
    );
    console.log("=== END getAppropriateMedia ===\n");

    return appropriateMedia[0];
  }

  renderMediaElement(media, altText) {
    const filename = media.filename || "";
    const ext = filename.toLowerCase().split(".").pop();
    const isVideo = ext === "mp4" || ext === "webm";

    if (isVideo && this.showVideos) {
      return `
      <video class="model-media" autoplay loop muted playsinline>
        <source src="images/${media.filename}" type="video/${ext.replace(
        ".",
        ""
      )}">
        <div class="model-placeholder">🎬</div>
      </video>
    `;
    } else if (isVideo && !this.showVideos) {
      // Video exists but videos are disabled - show placeholder
      return `<div class="model-placeholder">🎬</div>`;
    } else {
      return `<img src="images/${media.filename}" alt="${altText}" class="model-media">`;
    }
  }

  renderSettingsInputs(model) {
    const settings = model.recommendedSettings || {};
    const modelType = model.modelType || "checkpoint";

    // Define fields per model type
    const fieldDefinitions = {
      checkpoint: [
        { key: "resolution", placeholder: "Resolution (e.g., 512x768)" },
        { key: "sampler", placeholder: "Sampler" },
        { key: "steps", placeholder: "Steps" },
        { key: "cfg", placeholder: "CFG Scale" },
        { key: "clipSkip", placeholder: "Clip Skip" },
      ],
      lora: [
        { key: "weight", placeholder: "Weight (e.g., 0.7)" },
        { key: "resolution", placeholder: "Resolution (e.g., 512x768)" },
        { key: "steps", placeholder: "Steps" },
        { key: "cfg", placeholder: "CFG Scale" },
      ],
      controlnet: [
        { key: "preprocessor", placeholder: "Preprocessor" },
        { key: "weight", placeholder: "Weight (e.g., 0.8)" },
        { key: "guidanceStart", placeholder: "Guidance Start (e.g., 0.0)" },
        { key: "guidanceEnd", placeholder: "Guidance End (e.g., 1.0)" },
      ],
      upscaler: [
        { key: "scale", placeholder: "Scale (e.g., 4x)" },
        { key: "tileSize", placeholder: "Tile Size" },
      ],
      vae: [],
      embedding: [{ key: "weight", placeholder: "Weight (e.g., 1.0)" }],
      hypernetwork: [{ key: "weight", placeholder: "Weight (e.g., 0.8)" }],
    };

    const fields = fieldDefinitions[modelType] || fieldDefinitions.checkpoint;

    return fields
      .map(
        (field, idx) => `
    <input 
      type="text" 
      class="form-input" 
      name="${field.key}" 
      value="${settings[field.key] || ""}" 
      placeholder="${field.placeholder}"
      ${idx > 0 ? 'style="margin-top: 8px;"' : ""}
    >
  `
      )
      .join("");
  }

  updateModelCount() {
    const count = this.filteredModels.length;
    const total = this.modelData
      ? Object.keys(this.modelData.models).length
      : 0;
    const text =
      count === total ? `${total} models` : `${count} of ${total} models`;
    document.getElementById("modelCount").textContent = text;
  }

  getModelTypeIcon(type) {
    const icons = {
      checkpoint: "🎨",
      lora: "✨",
      controlnet: "🎮",
      upscaler: "🔍",
      vae: "🌈",
      embedding: "📦",
      hypernetwork: "🧠",
      clip: "📎",
      diffusion: "🌊",
    };
    return icons[type] || "📄";
  }

  formatKey(key) {
    return key
      .replace(/([A-Z])/g, " $1")
      .replace(/^./, (str) => str.toUpperCase());
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  escapeAttribute(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/'/g, "&#39;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  setupDragDrop() {
    const grid = document.getElementById("modelGrid");

    // Prevent default drag behaviors
    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      grid.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    // Add drag-over visual feedback
    grid.addEventListener("dragover", (e) => {
      const card = e.target.closest(".model-card");
      if (card) {
        card.classList.add("drag-over");
      }
    });

    grid.addEventListener("dragleave", (e) => {
      const card = e.target.closest(".model-card");
      if (card && !card.contains(e.relatedTarget)) {
        card.classList.remove("drag-over");
      }
    });

    // Handle file drop
    grid.addEventListener("drop", async (e) => {
      // Remove drag-over class from all cards
      document.querySelectorAll(".model-card.drag-over").forEach((card) => {
        card.classList.remove("drag-over");
      });

      const files = e.dataTransfer.files;
      if (files.length === 0) return;

      const file = files[0];
      const validExts = [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".mp4",
        ".webm",
      ];
      const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0];

      if (!validExts.includes(ext)) {
        this.showToast("❌ Invalid file type. Use images or videos.");
        return;
      }

      // Find which card was dropped on
      const card = e.target.closest(".model-card");
      if (!card) {
        this.showToast("❌ Drop file on a model card");
        return;
      }

      const modelPath = card.dataset.modelPath;
      if (!modelPath) return;

      await this.handleMediaDrop(file, modelPath);
    });
  }

  async handleMediaDrop(file, modelPath) {
    try {
      this.showToast("⏳ Uploading...");

      // Upload file to server
      const formData = new FormData();
      formData.append("file", file);
      formData.append("modelPath", modelPath);

      const response = await fetch("/api/upload-media", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const result = await response.json();

      // Show rating dialog
      const rating = await this.promptForRating();
      if (!rating) {
        this.showToast("❌ Upload cancelled");
        return;
      }

      // Update model with new media
      const updateResponse = await fetch(
        `/api/models/${encodeURIComponent(modelPath)}/add-media`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: result.filename,
            rating: rating,
            caption: "",
          }),
        }
      );

      if (updateResponse.ok) {
        this.showToast("✅ Media added successfully!");
        await this.loadFromServer(); // Reload data

        // Re-select the model if it was selected
        if (this.selectedModel?.path === modelPath) {
          this.selectedModel = this.modelData.models[modelPath];
          this.renderDetails(this.selectedModel);
        }
      }
    } catch (error) {
      console.error("Media upload failed:", error);
      this.showToast("❌ Failed to upload media");
    }
  }

  async promptForRating() {
    return new Promise((resolve) => {
      const dialog = document.createElement("div");
      dialog.className = "rating-dialog-overlay";
      dialog.innerHTML = `
      <div class="rating-dialog">
        <h3>Assign Content Rating</h3>
        <p style="color: #6272a4; margin-bottom: 20px; font-size: 14px;">
          Choose the content rating for this image/video
        </p>
        <div class="rating-options">
          <button class="rating-btn" data-rating="pg">🟢 PG</button>
          <button class="rating-btn" data-rating="r">🟡 R</button>
          <button class="rating-btn" data-rating="x">🔴 X</button>
        </div>
        <button class="btn-cancel">Cancel</button>
      </div>
    `;

      document.body.appendChild(dialog);

      dialog.addEventListener("click", (e) => {
        if (e.target.classList.contains("rating-btn")) {
          const rating = e.target.dataset.rating;
          dialog.remove();
          resolve(rating);
        } else if (
          e.target.classList.contains("btn-cancel") ||
          e.target === dialog
        ) {
          dialog.remove();
          resolve(null);
        }
      });
    });
  }
}

// Initialize app
const app = new ModelExplorer();

// App will auto-load from server in init()
console.log("🎨 Model Explorer initialized in Flask server mode");
