/**
 * StatusBar Component - Shows connection status and statistics
 */
export class StatusBar {
  constructor(container, store) {
    this.container = container;
    this.store = store;

    this.render();

    // Subscribe to store changes
    this.store.subscribe((state) => {
      this.update(state);
    });
  }

  render() {
    this.container.innerHTML = `
      <div class="status-indicator">
        <div class="status-dot"></div>
        <span class="status-text">Initializing...</span>
      </div>
      <div class="status-stats">
        <span class="model-count">0 models loaded</span>
        <span class="separator">•</span>
        <span class="notes-count">0 with notes</span>
      </div>
    `;

    this.statusDot = this.container.querySelector(".status-dot");
    this.statusText = this.container.querySelector(".status-text");
    this.modelCount = this.container.querySelector(".model-count");
    this.notesCount = this.container.querySelector(".notes-count");
  }

  update(state) {
    // Update connection status
    const isConnected = state.comfyUIConnected;
    this.statusDot.className = `status-dot ${isConnected ? "connected" : ""}`;
    this.statusText.textContent = isConnected
      ? "Connected to ComfyUI (localhost:8188)"
      : "ComfyUI not detected";

    // Update statistics
    const models = state.models || [];
    const modelsWithNotes = models.filter((m) => m.has_notes).length;

    this.modelCount.textContent = `${models.length} models loaded`;
    this.notesCount.textContent = `${modelsWithNotes} with custom notes`;
  }
}
