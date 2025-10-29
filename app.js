// ComfyUI Model Explorer - Main Application
class ModelExplorer {
  constructor() {
    this.modelData = null;
    this.filteredModels = [];
    this.selectedModel = null;
    this.nsfwFilterEnabled = true;
    this.isDirty = false;

    this.init();
  }

  init() {
    // Setup event listeners
    document.getElementById("loadJsonBtn").addEventListener("click", () => {
      document.getElementById("jsonFileInput").click();
    });

    document.getElementById("jsonFileInput").addEventListener("change", (e) => {
      this.loadJsonFile(e.target.files[0]);
    });

    document.getElementById("exportJsonBtn").addEventListener("click", () => {
      this.exportJson();
    });

    document.getElementById("nsfwToggle").addEventListener("click", () => {
      this.toggleNsfwFilter();
    });

    // Search and filter listeners
    document.getElementById("searchInput").addEventListener("input", () => {
      this.applyFilters();
    });

    document.getElementById("typeFilter").addEventListener("change", () => {
      this.applyFilters();
    });

    document
      .getElementById("baseModelFilter")
      .addEventListener("change", () => {
        this.applyFilters();
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

    // Keyboard shortcuts
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.closeEditModal();
      }
    });

    // Warn on leave if dirty
    window.addEventListener("beforeunload", (e) => {
      if (this.isDirty) {
        e.preventDefault();
        e.returnValue =
          "You have unsaved changes. Are you sure you want to leave?";
      }
    });

    // Auto-save to localStorage
    setInterval(() => {
      if (this.modelData && this.isDirty) {
        this.autoSave();
      }
    }, 30000); // Every 30 seconds
  }

  loadJsonFile(file) {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        this.modelData = data;
        this.isDirty = false; // Fresh load, no changes yet
        this.processModels();
        this.renderModelGrid();
        this.updateModelCount();

        // Enable export button and reset text
        const exportBtn = document.getElementById("exportJsonBtn");
        exportBtn.disabled = false;
        exportBtn.textContent = "💾 Export JSON";
        exportBtn.title = "Export database to file";

        // Hide welcome screen
        const welcomeScreen = document.getElementById("welcomeScreen");
        if (welcomeScreen) {
          welcomeScreen.remove();
        }

        console.log("✅ Loaded", Object.keys(data.models).length, "models");
        this.showToast("✅ Database loaded successfully!");
      } catch (error) {
        alert("Error loading JSON file: " + error.message);
        console.error("JSON parse error:", error);
      }
    };
    reader.readAsText(file);
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
    const typeFilter = document.getElementById("typeFilter").value;
    const baseModelFilter = document.getElementById("baseModelFilter").value;
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

        // Type filter
        if (typeFilter && model.modelType !== typeFilter) {
          return false;
        }

        // Base model filter
        if (baseModelFilter && model.baseModel !== baseModelFilter) {
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

    this.filteredModels.forEach((model) => {
      const card = this.createModelCard(model);
      grid.appendChild(card);
    });
  }

  createModelCard(model) {
    const card = document.createElement("div");
    card.className = "model-card";

    if (this.selectedModel?.path === model.path) {
      card.classList.add("selected");
    }

    // NSFW filtering
    if (model.nsfw && this.nsfwFilterEnabled) {
      const hasSfwImage = model.exampleImages?.some((img) => img.isSfw);
      if (!hasSfwImage) {
        card.classList.add("nsfw-hidden");
      }
    }

    // Get first image or placeholder
    let imageHtml;
    if (model.exampleImages && model.exampleImages.length > 0) {
      let displayImage;

      if (this.nsfwFilterEnabled && model.nsfw) {
        // NSFW filter ON (locked) - prefer SFW images
        displayImage =
          model.exampleImages.find((img) => img.isSfw) ||
          model.exampleImages[0];
      } else {
        // NSFW filter OFF (unlocked) - prefer NSFW images for NSFW models
        if (model.nsfw) {
          displayImage =
            model.exampleImages.find((img) => !img.isSfw) ||
            model.exampleImages[0];
        } else {
          displayImage = model.exampleImages[0];
        }
      }

      imageHtml = `<img src="images/${displayImage.filename}" alt="${model.name}" class="model-image">`;
    } else {
      const icon = this.getModelTypeIcon(model.modelType);
      imageHtml = `<div class="model-placeholder">${icon}</div>`;
    }

    card.innerHTML = `
            ${imageHtml}
            ${model.nsfw ? '<div class="nsfw-badge">NSFW</div>' : ""}
            <div class="model-info">
                <div class="model-header">
                    <div class="model-name">${this.escapeHtml(
                      model.name || "Unnamed Model"
                    )}</div>
                    <div class="favorite-icon" onclick="event.stopPropagation(); app.toggleFavorite('${
                      model.path
                    }')">
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
                ${
                  model.recommendedSettings &&
                  Object.keys(model.recommendedSettings).length > 0
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">⚙️ Recommended Settings</div>
                    </div>
                    <div class="info-grid">
                        ${Object.entries(model.recommendedSettings)
                          .map(
                            ([key, value]) => `
                            <div class="info-item">
                                <span class="info-label">${this.formatKey(
                                  key
                                )}</span>
                                <span class="info-value">${this.escapeHtml(
                                  value
                                )}</span>
                            </div>
                        `
                          )
                          .join("")}
                    </div>
                </div>
                `
                    : ""
                }

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
                          .map((img) => {
                            if (
                              this.nsfwFilterEnabled &&
                              model.nsfw &&
                              !img.isSfw
                            ) {
                              return ""; // Skip NSFW images when filter is on
                            }
                            return `
                                <div class="gallery-image">
                                    <img src="images/${img.filename}" alt="${
                              img.caption || model.name
                            }">
                                </div>
                            `;
                          })
                          .join("")}
                    </div>
                </div>
                `
                    : ""
                }
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
                    <label class="form-label">Notes</label>
                    <textarea class="form-textarea" name="notes" placeholder="Add your notes here...">${this.escapeHtml(
                      model.notes || ""
                    )}</textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">Recommended Settings</label>
                    <input type="text" class="form-input" name="resolution" value="${
                      model.recommendedSettings?.resolution || ""
                    }" placeholder="Resolution (e.g., 512x768)">
                    <input type="text" class="form-input" name="sampler" value="${
                      model.recommendedSettings?.sampler || ""
                    }" placeholder="Sampler" style="margin-top: 8px;">
                    <input type="text" class="form-input" name="steps" value="${
                      model.recommendedSettings?.steps || ""
                    }" placeholder="Steps" style="margin-top: 8px;">
                    <input type="text" class="form-input" name="cfg" value="${
                      model.recommendedSettings?.cfg || ""
                    }" placeholder="CFG Scale" style="margin-top: 8px;">
                    <input type="text" class="form-input" name="clipSkip" value="${
                      model.recommendedSettings?.clipSkip || ""
                    }" placeholder="Clip Skip" style="margin-top: 8px;">
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

    // Update recommended settings
    model.recommendedSettings = {
      ...(formData.get("resolution") && {
        resolution: formData.get("resolution"),
      }),
      ...(formData.get("sampler") && { sampler: formData.get("sampler") }),
      ...(formData.get("steps") && { steps: formData.get("steps") }),
      ...(formData.get("cfg") && { cfg: formData.get("cfg") }),
      ...(formData.get("clipSkip") && { clipSkip: formData.get("clipSkip") }),
    };

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

  toggleFavorite(path) {
    const model = this.modelData.models[path];
    model.favorite = !model.favorite;
    this.isDirty = true;
    this.autoSave(); // Save immediately
    this.applyFilters();

    if (this.selectedModel?.path === path) {
      this.selectedModel.favorite = model.favorite;
      this.renderDetails(this.selectedModel);
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

  autoSave() {
    if (!this.modelData) return;

    try {
      localStorage.setItem("modeldb_autosave", JSON.stringify(this.modelData));
      localStorage.setItem("modeldb_autosave_time", new Date().toISOString());
      console.log("💾 Auto-saved to localStorage");

      // Update visual indicator
      const exportBtn = document.getElementById("exportJsonBtn");
      if (this.isDirty) {
        exportBtn.textContent = "💾 Export JSON *";
        exportBtn.title = "You have unsaved changes";
      }
    } catch (error) {
      console.warn("Auto-save failed:", error);
      if (error.name === "QuotaExceededError") {
        alert(
          "Storage quota exceeded! Please export your JSON to save changes."
        );
      }
    }
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
}

// Initialize app
const app = new ModelExplorer();

// Auto-load modeldb.json on page load
window.addEventListener("load", async () => {
  // First, try to load from the same directory
  try {
    const response = await fetch("modeldb.json");
    if (response.ok) {
      const data = await response.json();
      console.log("✅ Auto-loaded modeldb.json from root directory");

      // Check if there's newer localStorage data
      const autosave = localStorage.getItem("modeldb_autosave");
      const autosaveTime = localStorage.getItem("modeldb_autosave_time");

      if (autosave && autosaveTime) {
        const minutes = Math.floor(
          (Date.now() - new Date(autosaveTime)) / 60000
        );
        if (minutes < 60) {
          if (
            confirm(
              `Found local edits from ${minutes} minutes ago. Load local edits instead of file?`
            )
          ) {
            app.modelData = JSON.parse(autosave);
            console.log("✅ Using local edits");
          } else {
            app.modelData = data;
          }
        } else {
          app.modelData = data;
        }
      } else {
        app.modelData = data;
      }

      app.processModels();
      app.renderModelGrid();
      app.updateModelCount();
      document.getElementById("exportJsonBtn").disabled = false;
      const welcomeScreen = document.getElementById("welcomeScreen");
      if (welcomeScreen) welcomeScreen.remove();
      return;
    }
  } catch (error) {
    console.log("ℹ️ No modeldb.json in root, waiting for manual load");
  }

  // If no file found, check for localStorage backup
  const autosave = localStorage.getItem("modeldb_autosave");
  const autosaveTime = localStorage.getItem("modeldb_autosave_time");

  if (autosave && autosaveTime) {
    const minutes = Math.floor((Date.now() - new Date(autosaveTime)) / 60000);
    if (minutes < 60) {
      if (
        confirm(
          `No modeldb.json found. Restore from local backup (${minutes} minutes ago)?`
        )
      ) {
        try {
          app.modelData = JSON.parse(autosave);
          app.processModels();
          app.renderModelGrid();
          app.updateModelCount();
          document.getElementById("exportJsonBtn").disabled = false;
          const welcomeScreen = document.getElementById("welcomeScreen");
          if (welcomeScreen) welcomeScreen.remove();
          console.log("✅ Restored from local backup");
        } catch (error) {
          console.error("Failed to restore backup:", error);
        }
      }
    }
  }
});
