/**
 * SearchBar Component - Handles search and filtering
 */
export class SearchBar {
  constructor(container, store) {
    this.container = container;
    this.store = store;
    this.debounceTimer = null;

    this.render();
    this.attachEvents();
  }

  render() {
    const state = this.store.getState();
    const filters = state.filters || {};

    // Don't replace the entire filter section, just ensure our elements exist
    if (!this.container.querySelector(".search-box")) {
      this.container.innerHTML = `
        <input type="text" 
               class="search-box" 
               placeholder="Search models..." 
               value="${filters.search || ""}">
        <div class="model-types">
          <div class="type-filter ${
            filters.type === "all" ? "active" : ""
          }" data-type="all">
            All
          </div>
          <div class="type-filter ${
            filters.type === "checkpoint" ? "active" : ""
          }" data-type="checkpoint">
            Checkpoints
          </div>
          <div class="type-filter ${
            filters.type === "lora" ? "active" : ""
          }" data-type="lora">
            LoRAs
          </div>
          <div class="type-filter ${
            filters.type === "vae" ? "active" : ""
          }" data-type="vae">
            VAE
          </div>
          <div class="type-filter ${
            filters.type === "controlnet" ? "active" : ""
          }" data-type="controlnet">
            ControlNet
          </div>
        </div>
      `;
    }

    this.searchInput = this.container.querySelector(".search-box");
    this.typeFilters = this.container.querySelectorAll(".type-filter");
  }

  attachEvents() {
    // Search input with debouncing
    this.searchInput.addEventListener("input", (e) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.handleSearch(e.target.value);
      }, 300);
    });

    // Type filters
    this.typeFilters.forEach((filter) => {
      filter.addEventListener("click", () => {
        const type = filter.dataset.type;
        this.handleTypeFilter(type);
      });
    });

    // Subscribe to store changes
    this.store.subscribe((state, changes) => {
      if (changes.filters) {
        this.updateUI(state.filters);
      }
    });
  }

  handleSearch(value) {
    const currentFilters = this.store.getState("filters");
    this.store.setState(
      {
        filters: {
          ...currentFilters,
          search: value,
        },
      },
      { debounce: 0 }
    );
  }

  // Fix the handleTypeFilter method to properly update active states
  handleTypeFilter(type) {
    const currentFilters = this.store.getState("filters");

    // Update store
    this.store.setState({
      filters: {
        ...currentFilters,
        type: type,
      },
    });

    // Update UI immediately
    this.updateFilterButtons(type);
  }

  updateFilterButtons(activeType) {
    this.typeFilters.forEach((filter) => {
      const isActive = filter.dataset.type === activeType;
      if (isActive) {
        filter.classList.add("active");
      } else {
        filter.classList.remove("active");
      }
    });
  }

  updateUI(filters) {
    // Update search input if needed
    if (this.searchInput && this.searchInput.value !== filters.search) {
      this.searchInput.value = filters.search || "";
    }

    // Update type filter buttons
    this.updateFilterButtons(filters.type || "all");
  }

  focus() {
    this.searchInput.focus();
    this.searchInput.select();
  }

  clear() {
    this.searchInput.value = "";
    this.handleSearch("");
  }
}
