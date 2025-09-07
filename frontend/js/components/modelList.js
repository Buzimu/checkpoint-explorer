/**
 * ModelList Component - Displays and manages the model list in the sidebar
 */
export class ModelList {
  constructor(container, store, api) {
    this.container = container;
    this.store = store;
    this.api = api;
    this.selectedId = null;

    // Bind methods
    this.render = this.render.bind(this);
    this.handleModelClick = this.handleModelClick.bind(this);
    this.handleFilterChange = this.handleFilterChange.bind(this);

    // Subscribe to store changes
    this.unsubscribe = store.subscribe((state, changes) => {
      // Only re-render if relevant data changed
      if (changes.models || changes.filters || changes.selectedModel) {
        this.render(state);
      }
    });

    // Initial render
    this.render(store.getState());
  }

  render(state) {
    const filteredModels = this.getFilteredModels(state);
    this.selectedId = state.selectedModel?.id || null;

    // Clear container
    this.container.innerHTML = "";

    if (filteredModels.length === 0) {
      this.renderEmptyState(state.filters);
      return;
    }

    // Create model items
    const fragment = document.createDocumentFragment();

    filteredModels.forEach((model) => {
      const modelElement = this.createModelElement(model);
      fragment.appendChild(modelElement);
    });

    this.container.appendChild(fragment);
  }

  createModelElement(model) {
    const div = document.createElement("div");
    div.className = `model-item ${
      model.id === this.selectedId ? "active" : ""
    }`;
    div.dataset.modelId = model.id;

    div.innerHTML = `
      <div class="model-name">${this.escapeHtml(model.name)}</div>
      <div class="model-meta">
        <span class="model-type">${model.type}</span>
        <span class="model-size">${model.size_formatted || model.size}</span>
      </div>
      ${
        model.has_notes
          ? '<span class="has-notes-indicator" title="Has notes">📝</span>'
          : ""
      }
    `;

    // Add click handler
    div.addEventListener("click", () => this.handleModelClick(model));

    return div;
  }

  renderEmptyState(filters) {
    const hasFilters =
      filters.search || (filters.type && filters.type !== "all");

    this.container.innerHTML = `
      <div class="no-models">
        ${
          hasFilters
            ? "<p>No models found matching your criteria.</p><p>Try adjusting your filters.</p>"
            : "<p>No models found.</p><p>Configure your models directory in settings.</p>"
        }
      </div>
    `;
  }

  // Make sure the filter comparison is case-insensitive and handles 'all'
  getFilteredModels(state) {
    let models = [...(state.models || [])];
    const filters = state.filters || {};

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

    // Apply type filter - fixed comparison
    if (filters.type && filters.type !== "all") {
      models = models.filter((m) => {
        // Handle different case variations
        const modelType = (m.type || "").toLowerCase();
        const filterType = filters.type.toLowerCase();

        // Map common variations
        const typeMap = {
          checkpoint: ["checkpoint", "ckpt"],
          lora: ["lora"],
          vae: ["vae"],
          controlnet: ["controlnet", "control"],
          embedding: ["embedding", "textual inversion", "ti"],
        };

        // Check if model type matches filter
        if (typeMap[filterType]) {
          return typeMap[filterType].some((t) => modelType.includes(t));
        }

        return modelType === filterType;
      });
    }

    // Apply has notes filter
    if (filters.hasNotes !== undefined && filters.hasNotes !== null) {
      models = models.filter((m) => m.has_notes === filters.hasNotes);
    }

    return models;
  }

  handleModelClick(model) {
    // Update store
    this.store.setState({ selectedModel: model });

    // Emit custom event
    document.dispatchEvent(
      new CustomEvent("model:selected", {
        detail: model,
      })
    );

    // Scroll into view if needed
    const element = this.container.querySelector(
      `[data-model-id="${model.id}"]`
    );
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  handleFilterChange(filterType, value) {
    const currentFilters = this.store.getState("filters");
    this.store.setState({
      filters: {
        ...currentFilters,
        [filterType]: value,
      },
    });
  }

  escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  destroy() {
    if (this.unsubscribe) {
      this.unsubscribe();
    }
    this.container.innerHTML = "";
  }
}
