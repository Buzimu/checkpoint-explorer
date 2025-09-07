/**
 * NotesEditor Component - Rich notes editing interface
 */
export class NotesEditor {
  constructor(container, store, api) {
    this.container = container || this.createContainer();
    this.store = store;
    this.api = api;
    this.isOpen = false;
    this.isDirty = false;
    this.currentModel = null;
    this.originalContent = "";
    this.autoSaveTimer = null;

    this.render();
  }

  createContainer() {
    const modal = document.createElement("div");
    modal.id = "notes-editor-modal";
    modal.className = "notes-editor-modal";
    modal.style.display = "none";
    document.body.appendChild(modal);
    return modal;
  }

  render() {
    this.container.innerHTML = `
      <div class="notes-editor-content">
        <div class="notes-editor-header">
          <h3 class="notes-editor-title">
            📝 Edit Notes: <span id="notes-model-name">Model</span>
          </h3>
          <button class="modal-close" title="Close (Esc)">×</button>
        </div>
        
        <div class="notes-editor-toolbar">
          <div class="toolbar-group">
            <button class="toolbar-btn" data-format="bold" title="Bold">
              <strong>B</strong>
            </button>
            <button class="toolbar-btn" data-format="italic" title="Italic">
              <em>I</em>
            </button>
            <button class="toolbar-btn" data-format="code" title="Code">
              &lt;/&gt;
            </button>
          </div>
          
          <div class="toolbar-separator"></div>
          
          <div class="toolbar-group">
            <button class="toolbar-btn" data-format="heading" title="Heading">
              H
            </button>
            <button class="toolbar-btn" data-format="list" title="List">
              ≡
            </button>
            <button class="toolbar-btn" data-format="separator" title="Separator">
              ─
            </button>
          </div>
          
          <div class="toolbar-separator"></div>
          
          <div class="toolbar-group">
            <select class="template-select" title="Apply template">
              <option value="">Templates...</option>
              <option value="checkpoint">Checkpoint Template</option>
              <option value="lora">LoRA Template</option>
              <option value="vae">VAE Template</option>
              <option value="controlnet">ControlNet Template</option>
              <option value="embedding">Embedding Template</option>
            </select>
          </div>
        </div>
        
        <div class="notes-editor-body">
          <textarea 
            id="notes-textarea"
            class="notes-textarea"
            placeholder="Enter your notes here...
            
Use Markdown formatting:
- **bold text** for emphasis
- *italic text* for subtle emphasis  
- \`code\` for settings or technical terms
- ## Headings for organization
- - List items for organization

Tips:
- Auto-save happens every 5 seconds
- Use Ctrl+S to save manually
- Templates available for different model types"
            spellcheck="true"></textarea>
        </div>
        
        <div class="notes-editor-footer">
          <div class="editor-status">
            <div class="auto-save-indicator">
              <span class="status-dot"></span>
              <span class="status-text">Ready</span>
            </div>
            <div class="word-count">
              <span id="char-count">0</span> characters,
              <span id="word-count">0</span> words
            </div>
          </div>
          
          <div class="editor-actions">
            <button class="btn btn-secondary" id="cancel-notes-btn">Cancel</button>
            <button class="btn btn-primary" id="save-notes-btn">Save & Close</button>
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
    const cancelBtn = this.container.querySelector("#cancel-notes-btn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => this.close());
    }

    // Save button
    const saveBtn = this.container.querySelector("#save-notes-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => this.saveAndClose());
    }

    // Textarea events
    const textarea = this.container.querySelector("#notes-textarea");
    if (textarea) {
      textarea.addEventListener("input", () => this.onInput());
      textarea.addEventListener("keydown", (e) => this.handleKeydown(e));
    }

    // Formatting buttons
    const formatBtns = this.container.querySelectorAll(
      ".toolbar-btn[data-format]"
    );
    formatBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        this.applyFormat(btn.dataset.format);
      });
    });

    // Template selector
    const templateSelect = this.container.querySelector(".template-select");
    if (templateSelect) {
      templateSelect.addEventListener("change", async (e) => {
        if (e.target.value) {
          await this.applyTemplate(e.target.value);
          e.target.value = "";
        }
      });
    }

    // Click outside to close
    this.container.addEventListener("click", (e) => {
      if (e.target === this.container) {
        this.confirmClose();
      }
    });
  }

  // In the open method, make sure we're using flex display
  async open(model) {
    if (!model) return;

    this.currentModel = model;
    this.isOpen = true;
    this.isDirty = false;

    // Update title
    const titleElement = this.container.querySelector("#notes-model-name");
    if (titleElement) {
      titleElement.textContent = model.name;
    }

    // Load existing notes
    try {
      const notesData = await this.api.getNotes(model.id);
      this.originalContent = notesData.content || "";

      const textarea = this.container.querySelector("#notes-textarea");
      if (textarea) {
        textarea.value = this.originalContent;
      }

      this.updateStats();
      this.updateStatus("saved");
    } catch (error) {
      console.error("Failed to load notes:", error);
      this.originalContent = "";
    }

    // Show modal with flex display for centering
    this.container.style.display = "flex";
    this.container.style.position = "fixed";
    this.container.style.top = "0";
    this.container.style.left = "0";
    this.container.style.right = "0";
    this.container.style.bottom = "0";
    this.container.style.alignItems = "center";
    this.container.style.justifyContent = "center";

    // Focus textarea
    setTimeout(() => {
      const textarea = this.container.querySelector("#notes-textarea");
      if (textarea) textarea.focus();
    }, 100);

    // Update store
    this.store.setState({
      ui: { ...this.store.getState("ui"), notesEditorOpen: true },
    });
  }

  close() {
    if (this.isDirty) {
      this.confirmClose();
    } else {
      this.forceClose();
    }
  }

  confirmClose() {
    if (this.isDirty) {
      const shouldClose = confirm(
        "You have unsaved changes. Are you sure you want to close?"
      );
      if (!shouldClose) return;
    }
    this.forceClose();
  }

  forceClose() {
    this.isOpen = false;
    this.isDirty = false;
    this.currentModel = null;
    this.originalContent = "";

    clearTimeout(this.autoSaveTimer);

    this.container.style.display = "none";

    // Update store
    this.store.setState({
      ui: { ...this.store.getState("ui"), notesEditorOpen: false },
    });
  }

  async save() {
    if (!this.currentModel) return false;

    const textarea = this.container.querySelector("#notes-textarea");
    const content = textarea ? textarea.value : "";

    this.updateStatus("saving");

    try {
      await this.api.saveNotes(this.currentModel.id, content, true);

      this.originalContent = content;
      this.isDirty = false;
      this.updateStatus("saved");

      // Update model in store
      const models = this.store.getState("models");
      const updatedModels = models.map((m) =>
        m.id === this.currentModel.id
          ? { ...m, has_notes: !!content.trim(), notes_content: content }
          : m
      );

      this.store.setState({
        models: updatedModels,
        selectedModel: updatedModels.find((m) => m.id === this.currentModel.id),
      });

      // Show notification
      document.dispatchEvent(
        new CustomEvent("notification:show", {
          detail: { message: "Notes saved successfully!", type: "success" },
        })
      );

      return true;
    } catch (error) {
      console.error("Failed to save notes:", error);
      this.updateStatus("error");

      document.dispatchEvent(
        new CustomEvent("notification:show", {
          detail: { message: "Failed to save notes", type: "error" },
        })
      );

      return false;
    }
  }

  async saveAndClose() {
    const saved = await this.save();
    if (saved) {
      this.forceClose();
    }
  }

  async autoSave() {
    if (this.isDirty && this.currentModel) {
      await this.save();
    }
  }

  onInput() {
    const textarea = this.container.querySelector("#notes-textarea");
    const content = textarea ? textarea.value : "";

    this.isDirty = content !== this.originalContent;
    this.updateStats();
    this.updateStatus(this.isDirty ? "dirty" : "saved");

    // Reset auto-save timer
    clearTimeout(this.autoSaveTimer);
    if (this.isDirty) {
      this.autoSaveTimer = setTimeout(() => this.autoSave(), 5000);
    }
  }

  handleKeydown(e) {
    // Save with Ctrl+S
    if (e.ctrlKey && e.key === "s") {
      e.preventDefault();
      this.save();
    }

    // Close with Escape (if no unsaved changes)
    if (e.key === "Escape" && !this.isDirty) {
      this.close();
    }
  }

  applyFormat(format) {
    const textarea = this.container.querySelector("#notes-textarea");
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = textarea.value.substring(start, end);

    let replacement = "";

    switch (format) {
      case "bold":
        replacement = `**${selectedText || "bold text"}**`;
        break;
      case "italic":
        replacement = `*${selectedText || "italic text"}*`;
        break;
      case "code":
        replacement = `\`${selectedText || "code"}\``;
        break;
      case "heading":
        replacement = `## ${selectedText || "Heading"}`;
        break;
      case "list":
        replacement = `- ${selectedText || "List item"}`;
        break;
      case "separator":
        replacement = "\n---\n";
        break;
    }

    const newContent =
      textarea.value.substring(0, start) +
      replacement +
      textarea.value.substring(end);

    textarea.value = newContent;

    // Set cursor position
    const newCursorPos = start + replacement.length;
    textarea.setSelectionRange(newCursorPos, newCursorPos);
    textarea.focus();

    this.onInput();
  }

  async applyTemplate(templateType) {
    if (!this.currentModel) return;

    const shouldReplace =
      !this.isDirty || confirm("Replace current content with template?");
    if (!shouldReplace) return;

    try {
      const result = await this.api.getNotesTemplate(
        this.currentModel.id,
        templateType
      );

      const textarea = this.container.querySelector("#notes-textarea");
      if (textarea && result.content) {
        textarea.value = result.content;
        this.onInput();

        document.dispatchEvent(
          new CustomEvent("notification:show", {
            detail: {
              message: `Applied ${templateType} template`,
              type: "success",
            },
          })
        );
      }
    } catch (error) {
      console.error("Failed to apply template:", error);
    }
  }

  updateStats() {
    const textarea = this.container.querySelector("#notes-textarea");
    const content = textarea ? textarea.value : "";

    const charCount = content.length;
    const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;

    const charElement = this.container.querySelector("#char-count");
    const wordElement = this.container.querySelector("#word-count");

    if (charElement) charElement.textContent = charCount;
    if (wordElement) wordElement.textContent = wordCount;
  }

  updateStatus(status) {
    const statusDot = this.container.querySelector(".status-dot");
    const statusText = this.container.querySelector(".status-text");

    const statusConfig = {
      saved: { color: "#50fa7b", text: "All changes saved" },
      dirty: { color: "#ffb86c", text: "Unsaved changes" },
      saving: { color: "#8be9fd", text: "Saving..." },
      error: { color: "#ff5555", text: "Error saving" },
    };

    const config = statusConfig[status] || statusConfig.saved;

    if (statusDot) {
      statusDot.style.backgroundColor = config.color;
    }

    if (statusText) {
      statusText.textContent = config.text;
    }
  }
}
