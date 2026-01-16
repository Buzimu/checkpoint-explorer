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
    this.activeVersions = {}; // Track active version index per model path

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
        "clip",
        "ipadapter",
        "unknown",
      ],
      baseModels: [
        "SD 1.5",
        "SDXL 1.0",
        "Flux",
        "Pony",
        "Illustrious",
        "Qwen",
        "WAN 2.1",
        "WAN 2.2",
        "unknown",
      ],
      contentRating: "pg",
      showVideos: false,
      favoritesOnly: false,
      hasImagesOnly: false,
      showMissing: false, // NEW: Filter for missing models
      showMismatch: false, // NEW: Filter for mismatched models
      showHashMismatch: false, // 🆕 NEW
      showMissingLink: false, // NEW: Filter for models without any URL links
    };

    // BUGFIX #4: Define valid types and bases for mismatch detection
    this.VALID_TYPES = [
      "checkpoint",
      "lora",
      "controlnet",
      "upscaler",
      "vae",
      "embedding",
      "hypernetwork",
      "clip",
      "ipadapter",
    ];
    this.VALID_BASES = [
      "SD 1.5",
      "SDXL 1.0",
      "Flux",
      "Pony",
      "Illustrious",
      "Qwen",
      "WAN 2.1",
      "WAN 2.2",
    ];

    this.init();
  }

  async loadActivityLog() {
    try {
      const response = await fetch("/api/activity-log");
      if (!response.ok) return;

      const result = await response.json();
      if (result.success) {
        this.updateActivityTicker(result.activities, result.upcoming || []);
      }
    } catch (error) {
      console.error("Failed to load activity log:", error);
    }
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
      .getElementById("closeImportModal")
      .addEventListener("click", () => {
        this.closeImportModal();
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

    document.getElementById("galleryBtn").addEventListener("click", () => {
      this.openGallery();
    });

    document
      .getElementById("detectNewerVersionsBtn")
      .addEventListener("click", () => {
        this.detectNewerVersions();
      });

    // Search and filter listeners - BUGFIX #2: Ensure filters apply immediately
    document.getElementById("searchInput").addEventListener("input", () => {
      console.log("🔍 Search input changed");
      this.applyFilters();
    });

    // Type checkbox listeners
    document
      .querySelectorAll('#typeCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.addEventListener("change", () => {
          console.log("📋 Type filter changed");
          this.applyFilters();
        });
      });

    // Base model checkbox listeners
    document
      .querySelectorAll('#baseCheckboxes input[type="checkbox"]')
      .forEach((cb) => {
        cb.addEventListener("change", () => {
          console.log("🏗️ Base filter changed");
          this.applyFilters();
        });
      });

    document
      .getElementById("favoritesFilter")
      .addEventListener("change", () => {
        console.log("⭐ Favorites filter changed");
        this.applyFilters();
      });

    document
      .getElementById("hasImagesFilter")
      .addEventListener("change", () => {
        console.log("🖼️ Has images filter changed");
        this.applyFilters();
      });

    // BUGFIX #4: New filter listeners
    document.getElementById("missingFilter").addEventListener("change", () => {
      console.log("⚠️ Missing filter changed");
      this.applyFilters();
    });

    document.getElementById("mismatchFilter").addEventListener("change", () => {
      console.log("🔀 Mismatch filter changed");
      this.applyFilters();
    });
    // Add listener
    document
      .getElementById("hashMismatchFilter")
      .addEventListener("change", () => {
        console.log("🚨 Hash mismatch filter changed");
        this.applyFilters();
      });

    document
      .getElementById("missingLinkFilter")
      .addEventListener("change", () => {
        console.log("🔗 Missing link filter changed");
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

    // Reset filters to defaults on load
    this.resetFiltersToDefaults();

    // Setup drag and drop
    this.setupDragDrop();

    // Auto-load from server
    this.loadFromServer();

    // Start activity log polling
    setInterval(() => {
      this.loadActivityLog();
    }, 5000); // Update every 5 seconds

    // Load immediately
    this.loadActivityLog();
  }

  getLinkType(mainPath, relatedPath) {
    /**
     * Get the link type between two models
     * Returns: 'confirmed', 'assumed', or null
     */
    const mainModel = this.modelData?.models?.[mainPath];
    if (!mainModel) return null;

    const linkMetadata = mainModel.linkMetadata || {};
    const metadata = linkMetadata[relatedPath];

    if (!metadata) return null;

    return metadata.type; // 'confirmed' or 'assumed'
  }

  getLinkTypeTooltip(linkType, versionName) {
    /**
     * Get tooltip text for link type
     */
    if (linkType === "confirmed") {
      return `✅ Confirmed: ${versionName} (Both have CivitAI links)`;
    } else if (linkType === "assumed") {
      return `🔍 Assumed: ${versionName} (Matched by file size - add CivitAI link to confirm)`;
    } else {
      return versionName;
    }
  }

  // Add this method to the ModelExplorer class

  async openGallery() {
    try {
      this.showToast("⏳ Loading gallery...");

      const response = await fetch("/api/gallery");

      if (response.ok) {
        const result = await response.json();
        console.log("🖼️ Gallery data:", result);

        // Show the gallery modal
        this.showGalleryModal(result);
      } else {
        const error = await response.json();
        this.showToast(
          `❌ Gallery load failed: ${error.error || "Unknown error"}`
        );
      }
    } catch (error) {
      console.error("Gallery load failed:", error);
      this.showToast("❌ Gallery load failed: " + error.message);
    }
  }

  showGalleryModal(galleryData) {
    const modal = document.getElementById("galleryModal");

    // Update stats
    document.getElementById("galleryTotalCount").textContent =
      galleryData.stats.total;
    document.getElementById("galleryOrphanedCount").textContent =
      galleryData.stats.orphaned;
    document.getElementById("galleryImagesCount").textContent =
      galleryData.stats.images;
    document.getElementById("galleryVideosCount").textContent =
      galleryData.stats.videos;

    // Store gallery data for filtering
    this.galleryData = galleryData.media;

    // Get current filters from header
    const currentRating = document.getElementById("contentRatingSelect").value;
    const showVideos = this.videoMode;

    // Render filtered gallery
    this.renderGalleryGrid(currentRating, showVideos);

    modal.style.display = "flex";
  }

  renderGalleryGrid(ratingFilter = "pg", showVideos = false) {
    const gridContainer = document.getElementById("galleryGrid");

    // Filter media based on rating and video mode
    const filtered = this.galleryData.filter((item) => {
      const ratingMatch = item.rating === ratingFilter;
      const typeMatch = showVideos ? true : !item.isVideo;
      return ratingMatch && typeMatch;
    });

    if (filtered.length === 0) {
      gridContainer.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #6272a4;">
          <p>No media found for the selected filters</p>
        </div>
      `;
      return;
    }

    // Render grid items
    gridContainer.innerHTML = filtered
      .map((item) => {
        const orphanedClass = item.orphaned ? "gallery-item-orphaned" : "";
        const orphanedLabel = item.orphaned
          ? '<span class="orphan-badge">⚠️ ORPHANED</span>'
          : "";

        if (item.isVideo) {
          return `
          <div class="gallery-item ${orphanedClass}" onclick="app.openGalleryMedia('${this.escapeAttribute(
            item.filename
          )}', ${item.orphaned}, '${this.escapeAttribute(
            item.modelPath || ""
          )}')">
            <video class="gallery-thumbnail" muted loop onmouseover="this.play()" onmouseout="this.pause()">
              <source src="images/${item.filename}" type="video/${item.filename
            .split(".")
            .pop()}">
            </video>
            ${orphanedLabel}
            <div class="gallery-item-info">
              <div class="gallery-item-name">${this.escapeHtml(
                item.modelName
              )}</div>
            </div>
          </div>
        `;
        } else {
          return `
          <div class="gallery-item ${orphanedClass}" onclick="app.openGalleryMedia('${this.escapeAttribute(
            item.filename
          )}', ${item.orphaned}, '${this.escapeAttribute(
            item.modelPath || ""
          )}')">
            <img class="gallery-thumbnail" src="images/${
              item.filename
            }" alt="${this.escapeHtml(item.modelName)}">
            ${orphanedLabel}
            <div class="gallery-item-info">
              <div class="gallery-item-name">${this.escapeHtml(
                item.modelName
              )}</div>
            </div>
          </div>
        `;
        }
      })
      .join("");
  }

  openGalleryMedia(filename, isOrphaned, modelPath) {
    if (isOrphaned) {
      // For orphaned media, open lightbox with delete option
      this.openOrphanedMediaLightbox(filename);
    } else {
      // For regular media, open existing lightbox
      const caption =
        this.galleryData.find((m) => m.filename === filename)?.modelName || "";
      this.openLightbox(filename, caption, modelPath);
    }
  }

  openOrphanedMediaLightbox(filename) {
    const lightbox = document.getElementById("imageLightbox");
    const lightboxContent = document.getElementById("lightboxContent");
    const lightboxCaption = document.getElementById("lightboxCaption");
    const lightboxControls = document.getElementById("lightboxControls");

    const ext = filename.toLowerCase();
    const isVideo = ext.endsWith(".mp4") || ext.endsWith(".webm");

    if (isVideo) {
      lightboxContent.innerHTML = `
        <video id="lightboxMedia" autoplay loop muted controls style="max-width: 90%; max-height: 90vh; border-radius: 8px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);">
          <source src="images/${filename}" type="video/${ext.split(".").pop()}">
        </video>
      `;
    } else {
      lightboxContent.innerHTML = `
        <img id="lightboxMedia" src="images/${filename}" alt="Orphaned media" style="max-width: 90%; max-height: 90vh; border-radius: 8px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);">
      `;
    }

    lightboxCaption.innerHTML = `⚠️ <strong>Orphaned File</strong> - This media is not linked to any model`;

    lightboxControls.innerHTML = `
      <div class="lightbox-rating-controls">
        <button class="btn-lightbox-delete" onclick="app.deleteOrphanedMedia('${this.escapeAttribute(
          filename
        )}')">🗑️ Delete Orphaned File</button>
      </div>
    `;

    lightbox.style.display = "flex";
  }

  async deleteOrphanedMedia(filename) {
    if (
      !confirm(
        `Are you sure you want to delete this orphaned file?\n\n${filename}\n\nThis action cannot be undone.`
      )
    ) {
      return;
    }

    try {
      const response = await fetch(
        `/api/media/${encodeURIComponent(filename)}`,
        {
          method: "DELETE",
        }
      );

      if (response.ok) {
        this.showToast("✅ Orphaned file deleted!");
        this.closeLightbox();
        // Refresh gallery
        await this.openGallery();
      } else {
        this.showToast("❌ Failed to delete file");
      }
    } catch (error) {
      console.error("Failed to delete file:", error);
      this.showToast("❌ Failed to delete file");
    }
  }

  closeGalleryModal() {
    const modal = document.getElementById("galleryModal");
    modal.style.display = "none";
    this.galleryData = null;
  }

  updateGalleryFilters() {
    const ratingSelect = document.getElementById("galleryRatingSelect");
    const videoToggle = document.getElementById("galleryVideoToggle");

    const rating = ratingSelect.value;
    const showVideos = videoToggle.dataset.mode === "both";

    this.renderGalleryGrid(rating, showVideos);
  }

  toggleGalleryVideoMode() {
    const btn = document.getElementById("galleryVideoToggle");
    const currentMode = btn.dataset.mode || "images";

    if (currentMode === "images") {
      btn.dataset.mode = "both";
      btn.innerHTML = "🎬 All Media";
      btn.title = "Showing images and videos (click for images only)";
    } else {
      btn.dataset.mode = "images";
      btn.innerHTML = "🖼️ Images";
      btn.title = "Showing images only (click to include videos)";
    }

    this.updateGalleryFilters();
  }

  async resetScrapeCooldowns() {
    try {
      console.log("🔄 Resetting scrape cooldowns...");

      const response = await fetch("/api/reset-scrape-cooldowns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        console.log("✅ Scrape cooldowns reset");
      } else {
        console.warn("⚠️ Failed to reset scrape cooldowns");
      }
    } catch (error) {
      console.error("Failed to reset scrape cooldowns:", error);
    }
  }

  async detectNewerVersions() {
    try {
      this.showToast("⏳ Checking for newer versions...");

      const response = await fetch("/api/detect-newer-versions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        const result = await response.json();

        console.log("✨ Newer Version Detection Results:", result);

        if (result.count > 0) {
          const message = `✨ Found ${result.count} model(s) with newer versions available!`;
          this.showToast(message);
        } else {
          this.showToast("✅ All models are up to date!");
        }

        // Reload database to show the new version badges
        await this.loadFromServer();
      } else {
        const error = await response.json();
        this.showToast(
          `❌ Version detection failed: ${error.error || "Unknown error"}`
        );
      }
    } catch (error) {
      console.error("Newer version detection failed:", error);
      this.showToast("❌ Version detection failed: " + error.message);
    }
  }

  // =====================================
  // HTML BUTTON TO ADD TO index.html
  // =====================================

  /*
Add this button to the header-right section in index.html:

<button class="btn btn-secondary" id="linkVersionsBtn" title="Link related model versions">
  🔗 Link Versions
</button>

Then add this listener in the init() method:

document.getElementById('linkVersionsBtn').addEventListener('click', () => {
  this.triggerVersionLinking();
});
*/

  // Get stack count for visual stacking (max 4)
  getStackCount(versionCount) {
    if (versionCount <= 1) return 0;
    return Math.min(versionCount - 1, 4);
  }

  // Get all versions for a model (main + related)
  getAllVersions(model) {
    const versions = [{ path: model.path, ...model }];

    if (model.relatedVersions && Array.isArray(model.relatedVersions)) {
      model.relatedVersions.forEach((relPath) => {
        const relModel = this.modelData.models[relPath];
        if (relModel) {
          versions.push({ path: relPath, ...relModel });
        }
      });
    }

    // 🆕 Sort versions by published date (newest first)
    versions.sort((a, b) => {
      const dateA = this.getModelPublishedDate(a);
      const dateB = this.getModelPublishedDate(b);

      // If both have dates, sort by date (newest first)
      if (dateA && dateB) {
        return new Date(dateB) - new Date(dateA);
      }

      // Models without dates go to the end
      if (!dateA && dateB) return 1;
      if (dateA && !dateB) return -1;

      // If neither has a date, maintain current order
      return 0;
    });

    return versions;
  }

  // Get active version for a model
  getActiveVersion(model) {
    const versions = this.getAllVersions(model);
    const activeIdx = this.activeVersions[model.path] || 0;
    return versions[activeIdx] || versions[0];
  }

  // Set active version for a model
  setActiveVersion(modelPath, versionIdx) {
    this.activeVersions[modelPath] = versionIdx;

    // ALWAYS update sidebar when a version tab is clicked
    const primaryModel = this.modelData.models[modelPath];
    if (!primaryModel) return;

    // FIX: Ensure primary model has path property (database models don't store path ON them)
    const modelWithPath = { path: modelPath, ...primaryModel };
    const versions = this.getAllVersions(modelWithPath);
    const newActiveVersion = versions[versionIdx];

    // Update selected model reference BEFORE rendering
    this.selectedModel = newActiveVersion;

    // Re-render grid with updated selection
    this.renderModelGrid();

    // Re-render details panel
    this.renderDetails(newActiveVersion);

    // Scroll the active tab into view after render completes
    // Use requestAnimationFrame to ensure DOM is fully updated
    requestAnimationFrame(() => {
      setTimeout(() => {
        // Find the card by primary path (stored in data-primary-path)
        const modelCard = document.querySelector(
          `.model-card[data-primary-path="${CSS.escape(modelPath)}"]`
        );
        if (modelCard) {
          const carousel = modelCard.querySelector(".version-carousel-scroll");
          const activeTab = modelCard.querySelector(".version-tab.active");
          if (activeTab && carousel) {
            // Scroll the carousel to center the active tab
            const carouselRect = carousel.getBoundingClientRect();
            const tabRect = activeTab.getBoundingClientRect();
            const scrollLeft =
              carousel.scrollLeft +
              (tabRect.left - carouselRect.left) -
              carouselRect.width / 2 +
              tabRect.width / 2;

            carousel.scrollTo({
              left: scrollLeft,
              behavior: "smooth",
            });
          }
        }
      }, 50);
    });
  }

  updateActivityTicker(activities, upcoming = []) {
    const tickerContent = document.getElementById("tickerContent");
    const tickerQueue = document.getElementById("tickerQueue");

    if (!tickerContent || !tickerQueue) return;

    // Update the main ticker with the current active task
    if (activities.length === 0 && upcoming.length === 0) {
      tickerContent.innerHTML = `
        <span class="ticker-text">No active tasks</span>
      `;
      tickerQueue.innerHTML = `
        <div class="ticker-queue-header">Task Queue</div>
        <div class="ticker-queue-empty">No pending tasks</div>
      `;
      return;
    }

    // Determine what to show in main ticker
    let tickerText = "";
    if (activities.length > 0) {
      const currentActivity = activities[0];
      tickerText = `${currentActivity.action}: ${currentActivity.modelName}`;
    } else if (upcoming.length > 0) {
      const nextTask = upcoming[0];
      const minutes = Math.floor(nextTask.secondsUntil / 60);
      const seconds = nextTask.secondsUntil % 60;
      const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
      tickerText = `Next: ${nextTask.task} in ${timeStr}`;
    }

    // Update main ticker display
    const textElement = `<span class="ticker-text ${
      tickerText.length > 50 ? "scrolling" : ""
    }">${tickerText}</span>`;

    tickerContent.innerHTML = textElement;

    // Build the queue display with BOTH history and upcoming
    let queueHTML = "";

    // Upcoming tasks section
    if (upcoming.length > 0) {
      queueHTML += '<div class="ticker-queue-header">Upcoming Tasks</div>';
      upcoming.forEach((task) => {
        const minutes = Math.floor(task.secondsUntil / 60);
        const seconds = task.secondsUntil % 60;
        const timeStr =
          minutes > 0 ? `in ${minutes}m ${seconds}s` : `in ${seconds}s`;

        queueHTML += `
          <div class="ticker-queue-item pending">
            <div class="ticker-queue-time">${timeStr}</div>
            <div class="ticker-queue-content">
              <span class="ticker-queue-icon">⏱️</span>
              <div class="ticker-queue-text">
                <strong>${task.task}</strong>
                <span class="ticker-queue-status pending">scheduled</span>
                ${
                  task.description
                    ? `<div class="ticker-queue-details">${task.description}</div>`
                    : ""
                }
              </div>
            </div>
          </div>
        `;
      });
    }

    // Recent activity section
    if (activities.length > 0) {
      queueHTML += '<div class="ticker-queue-header">Recent Activity</div>';
      activities.forEach((activity, index) => {
        const time = new Date(activity.timestamp).toLocaleTimeString();
        const icon = this.getActivityIcon(activity);
        const itemStatusClass =
          activity.status === "success"
            ? "success"
            : activity.status === "error"
            ? "error"
            : index === 0
            ? "active"
            : "pending";
        const statusBadge =
          index === 0
            ? "running"
            : activity.status === "success"
            ? "completed"
            : activity.status === "error"
            ? "failed"
            : "pending";

        queueHTML += `
          <div class="ticker-queue-item ${itemStatusClass}">
            <div class="ticker-queue-time">${time}</div>
            <div class="ticker-queue-content">
              <span class="ticker-queue-icon">${icon}</span>
              <div class="ticker-queue-text">
                <strong>${activity.action}</strong>: ${activity.modelName}
                <span class="ticker-queue-status ${statusBadge}">${statusBadge}</span>
                ${
                  activity.details
                    ? `<div class="ticker-queue-details">${activity.details}</div>`
                    : ""
                }
              </div>
            </div>
          </div>
        `;
      });
    }

    // If nothing to show
    if (queueHTML === "") {
      queueHTML = `
        <div class="ticker-queue-header">Task Queue</div>
        <div class="ticker-queue-empty">No tasks</div>
      `;
    }

    tickerQueue.innerHTML = queueHTML;
  }

  getActivityIcon(activity) {
    if (activity.status === "success") return "✅";
    if (activity.status === "error") return "❌";

    // Default icons based on action type
    if (activity.action && activity.action.toLowerCase().includes("scrape"))
      return "🔍";
    if (activity.action && activity.action.toLowerCase().includes("download"))
      return "⬇️";
    if (activity.action && activity.action.toLowerCase().includes("update"))
      return "🔄";
    if (activity.action && activity.action.toLowerCase().includes("scan"))
      return "📊";

    return "⚙️"; // Default gear icon
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

    // BUGFIX #4: Reset new filters
    document.getElementById("missingFilter").checked =
      this.DEFAULT_FILTERS.showMissing;
    document.getElementById("mismatchFilter").checked =
      this.DEFAULT_FILTERS.showMismatch;
    document.getElementById("missingLinkFilter").checked =
      this.DEFAULT_FILTERS.showMissingLink;

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
      this.processModels(); // This will tag mismatches
      this.applyFilters(); // BUGFIX #2: Explicit call after loading
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
    // BUGFIX #4: Tag models with mismatches during processing
    console.log("🔄 Processing models and tagging mismatches...");

    // Convert models object to array with keys
    this.filteredModels = Object.entries(this.modelData.models).map(
      ([path, model]) => {
        // Check for type mismatch
        const modelType = (model.modelType || "").toLowerCase();
        const hasTypeMismatch =
          modelType &&
          modelType !== "unknown" &&
          !this.VALID_TYPES.includes(modelType);

        // Check for base mismatch
        const baseModel = (model.baseModel || "").trim();
        const hasBaseMismatch =
          baseModel &&
          baseModel !== "unknown" &&
          !this.VALID_BASES.includes(baseModel);

        // Check for missing links
        const hasMissingLink =
          !model.civitaiUrl &&
          !model.huggingFaceUrl &&
          !model.githubUrl &&
          !model.otherUrl;

        // Tag model with mismatch status
        const modelWithFlags = {
          path,
          ...model,
          _hasMismatch: hasTypeMismatch || hasBaseMismatch,
          _typeMismatch: hasTypeMismatch,
          _baseMismatch: hasBaseMismatch,
          _hasMissingLink: hasMissingLink,
        };

        if (hasTypeMismatch || hasBaseMismatch) {
          console.log(`🔀 Mismatch detected: ${model.name}`, {
            type: model.modelType,
            base: model.baseModel,
            typeMismatch: hasTypeMismatch,
            baseMismatch: hasBaseMismatch,
          });
        }

        return modelWithFlags;
      }
    );

    // Sort by name
    this.filteredModels.sort((a, b) =>
      (a.name || "").localeCompare(b.name || "")
    );

    console.log("✅ Models processed");
  }

  applyFilters() {
    if (!this.modelData) {
      console.log("⚠️ No model data loaded yet");
      return;
    }

    console.log("\n🔍 === APPLY FILTERS START ===");

    const searchTerm = document
      .getElementById("searchInput")
      .value.toLowerCase();

    // Get selected types
    const selectedTypes = Array.from(
      document.querySelectorAll("#typeCheckboxes input:checked")
    ).map((cb) => cb.value);

    // Get selected base models
    const selectedBases = Array.from(
      document.querySelectorAll("#baseCheckboxes input:checked")
    ).map((cb) => cb.value);

    const favoritesOnly = document.getElementById("favoritesFilter").checked;
    const hasImagesOnly = document.getElementById("hasImagesFilter").checked;

    // BUGFIX #4: Get new filter states
    const showMissingOnly = document.getElementById("missingFilter").checked;
    const showMismatchOnly = document.getElementById("mismatchFilter").checked;
    const showHashMismatchOnly =
      document.getElementById("hashMismatchFilter").checked;
    const showMissingLinkOnly =
      document.getElementById("missingLinkFilter").checked;

    console.log("Filter settings:", {
      searchTerm,
      selectedTypes,
      selectedBases,
      favoritesOnly,
      hasImagesOnly,
      showMissingOnly,
      showMismatchOnly,
    });

    this.filteredModels = Object.entries(this.modelData.models)
      .map(([path, model]) => {
        // Re-check mismatch flags
        const modelType = (model.modelType || "").toLowerCase();
        const hasTypeMismatch =
          modelType &&
          modelType !== "unknown" &&
          !this.VALID_TYPES.includes(modelType);

        const baseModel = (model.baseModel || "").trim();
        const hasBaseMismatch =
          baseModel &&
          baseModel !== "unknown" &&
          !this.VALID_BASES.includes(baseModel);

        // Check for missing links
        const hasMissingLink =
          !model.civitaiUrl &&
          !model.huggingFaceUrl &&
          !model.githubUrl &&
          !model.otherUrl;

        return {
          path,
          ...model,
          _hasMismatch: hasTypeMismatch || hasBaseMismatch,
          _typeMismatch: hasTypeMismatch,
          _baseMismatch: hasBaseMismatch,
          _hasHashMismatch: model.hashMismatch?.detected || false,
          _hasMissingLink: hasMissingLink,
        };
      })
      .filter((model) => {
        // BUGFIX #1: Defensive check for tags array
        if (searchTerm) {
          const nameMatch = (model.name || "")
            .toLowerCase()
            .includes(searchTerm);
          const tagsMatch =
            Array.isArray(model.tags) &&
            model.tags.some((tag) =>
              (tag || "").toLowerCase().includes(searchTerm)
            );

          if (!nameMatch && !tagsMatch) {
            console.log(`  ❌ Search filter: ${model.name}`);
            return false;
          }
        }

        // Type filter
        if (selectedTypes.length === 0) {
          console.log(`  ❌ No types selected`);
          return false;
        }

        const modelType = model.modelType || "unknown";
        const isUnknownType =
          !modelType || modelType === "" || modelType === "unknown";

        // BUGFIX #9: Treat types not in VALID_TYPES as "unknown"
        // e.g., "diffusion", "clip", etc. should be caught by "unknown" checkbox
        const isInvalidType =
          modelType &&
          modelType !== "unknown" &&
          !this.VALID_TYPES.includes(modelType);

        if (
          selectedTypes.includes("unknown") &&
          (isUnknownType || isInvalidType)
        ) {
          // Allow through if "unknown" is selected
        } else if (!selectedTypes.includes(modelType)) {
          return false;
        }

        // Base model filter
        if (selectedBases.length === 0) {
          console.log(`  ❌ No bases selected`);
          return false;
        }

        const baseModel = model.baseModel || "unknown";
        const isUnknownBase =
          !baseModel || baseModel === "" || baseModel === "unknown";

        if (selectedBases.includes("unknown") && isUnknownBase) {
          // Allow through
        } else {
          // BUGFIX #7: Normalize baseModel comparison to handle variants
          // e.g., "SDXL 1.0" should match "SDXL 1.0", "SD 1.5" should match "SD 1.5"
          const normalizedBase = baseModel.replace(/\s+/g, "").toUpperCase();

          // BUGFIX #9: Check if this base is in our valid list
          const isInvalidBase =
            baseModel &&
            baseModel !== "unknown" &&
            !this.VALID_BASES.some((valid) => {
              const normalizedValid = valid.replace(/\s+/g, "").toUpperCase();
              return normalizedBase.startsWith(normalizedValid);
            });

          // If "unknown" is selected and this base is invalid/unrecognized, allow through
          if (selectedBases.includes("unknown") && isInvalidBase) {
            // Allow through
          } else {
            const matchesSelected = selectedBases.some((selected) => {
              const normalizedSelected = selected
                .replace(/\s+/g, "")
                .toUpperCase();
              // Check if the model's base starts with the selected base
              // This handles "SDXL 1.0" matching "SDXL 1.0", "SD 1.5 LCM" matching "SD 1.5"
              return (
                normalizedBase.startsWith(normalizedSelected) ||
                normalizedBase === normalizedSelected
              );
            });

            if (!matchesSelected) {
              return false;
            }
          }
        }

        // Favorites filter
        if (favoritesOnly && !model.favorite) {
          return false;
        }

        // BUGFIX #5: Has images filter with defensive array check
        if (hasImagesOnly) {
          const mediaArray = Array.isArray(model.exampleImages)
            ? model.exampleImages
            : [];

          if (mediaArray.length === 0) {
            console.log(`  ❌ Has images filter: ${model.name} has no images`);
            return false;
          }
        }

        // BUGFIX #4: Missing filter
        if (showMissingOnly && model._status !== "missing") {
          return false;
        }

        // BUGFIX #4: Mismatch filter
        if (showMismatchOnly && !model._hasMismatch) {
          return false;
        }
        if (showHashMismatchOnly && !model._hasHashMismatch) {
          return false;
        }

        // Missing link filter
        if (showMissingLinkOnly && !model._hasMissingLink) {
          return false;
        }

        // BUGFIX #8: Keep all models in filteredModels for accurate counting
        // Secondary versions will be filtered during rendering, not here
        return true;
      })
      .sort((a, b) => (a.name || "").localeCompare(b.name || ""));

    console.log(`✅ Filtered to ${this.filteredModels.length} models`);
    console.log("=== APPLY FILTERS END ===\n");

    // BUGFIX #2: Ensure render happens after filtering
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
      // BUGFIX #8: Skip secondary versions during rendering
      // They're counted in filteredModels but shown as stacks, not separate cards
      if (!this.isPrimaryVersion(model)) {
        console.log(
          `⏭️ Skipping secondary version: ${model.name} (part of version stack)`
        );
        return;
      }

      const card = this.createModelCard(model);
      if (card) {
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
    const isMissing = model._status === "missing";
    const isMismatch = model._hasMismatch;
    const hasHashMismatch = model.hashMismatch?.detected; // 🆕 NEW
    const hasNewerVersion = model.newVersionAvailable?.hasNewerVersion; // 🆕 NEW VERSION BADGE
    const hasMissingLink = model._hasMissingLink; // NEW: Missing link detection

    if (!this.canShowModel(model)) {
      return null;
    }

    // Get all versions (main model + related versions)
    const versions = this.getAllVersions(model);
    const stackCount = this.getStackCount(versions.length);
    const activeVersionIdx = this.activeVersions[model.path] || 0;
    const activeVersion = versions[activeVersionIdx];

    // Create wrapper for stacking
    const wrapper = document.createElement("div");
    wrapper.style.cssText =
      "position: relative; width: 100%; overflow: visible;";

    // Create stacked cards behind
    for (let i = 0; i < stackCount; i++) {
      const stackCard = document.createElement("div");
      const offset = (i + 1) * 10;
      const opacity = 0.8 - i * 0.1;
      const zIndex = stackCount - i;

      stackCard.style.cssText = `
      position: absolute;
      top: ${offset}px;
      left: ${offset}px;
      right: -${offset}px;
      bottom: -${offset}px;
      background: rgba(40, 42, 54, 0.95);
      border: 2px solid rgba(68, 71, 90, 0.8);
      border-radius: 12px;
      opacity: ${opacity};
      z-index: ${zIndex};
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
      pointer-events: none;
    `;
      wrapper.appendChild(stackCard);
    }

    // Create main card
    const card = document.createElement("div");
    card.className = "model-card";

    // 🔧 BUGFIX: Store the ACTIVE version's path, not the primary model's path
    // This ensures drag-dropped images go to the correct version
    card.dataset.modelPath = activeVersion.path;

    // Store the primary model path for version switching reference
    card.dataset.primaryPath = model.path;

    if (this.selectedModel?.path === model.path) {
      card.classList.add("selected");
    }

    card.style.cssText = `
    background: rgba(40, 42, 54, 0.95);
    border: ${
      this.selectedModel?.path === model.path
        ? "2px solid #ff79c6"
        : "2px solid #44475a"
    };
    border-radius: 12px;
    overflow: visible;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    width: 100%;
    min-height: 380px;
    display: flex;
    flex-direction: column;
    box-shadow: ${
      this.selectedModel?.path === model.path
        ? "0 0 0 3px rgba(255, 121, 198, 0.2), 0 12px 40px rgba(0, 0, 0, 0.4)"
        : "0 8px 20px rgba(0, 0, 0, 0.3)"
    };
    z-index: 100;
  `;

    // Badges - positioned below carousel if stacked, otherwise at top
    const badgeTopOffset = versions.length > 1 ? 60 : 12;
    const missingBadge = isMissing
      ? `<div class="missing-badge" style="top: ${
          badgeTopOffset + 30
        }px;">⚠️ MISSING</div>`
      : "";
    const mismatchBadge = isMismatch
      ? `<div class="missing-badge" style="top: ${badgeTopOffset}px;">🔀 MISMATCH</div>`
      : "";
    // 🆕 NEW: Hash mismatch badge (most critical!)
    const hashMismatchBadge = hasHashMismatch
      ? `<div class="missing-badge" style="top: ${
          badgeTopOffset + 60
        }px; background: rgba(255, 85, 85, 0.95);">🚨 WRONG VERSION</div>`
      : "";
    // 🆕 NEW VERSION BADGE: Indicates newer version available
    const newVersionBadge = hasNewerVersion
      ? `<div class="new-version-badge" style="top: ${badgeTopOffset}px;">✨ NEW VERSION</div>`
      : "";
    // Missing link badge
    const missingLinkBadge = hasMissingLink
      ? `<div class="missing-link-badge" style="top: ${badgeTopOffset}px;">🔗</div>`
      : "";

    // Version selector (carousel)
    let versionSelector = "";
    if (versions.length > 1) {
      const carouselId = `carousel-${model.path.replace(/[^a-z0-9]/gi, "-")}`;
      versionSelector = `
<div class="version-selector" style="
  padding: 12px;
  border-bottom: 1px solid #44475a;
  background: rgba(68, 71, 90, 0.4);
  backdrop-filter: blur(10px);
  position: relative;
  z-index: 200;
">
  <div class="version-carousel">
    <button class="carousel-nav-btn carousel-nav-prev" data-carousel-id="${carouselId}" title="Previous version">
      ‹
    </button>
    <div id="${carouselId}" class="version-carousel-scroll version-tabs">
      ${versions
        .map((v, idx) => {
          // Check link type for this version
          const linkType = this.getLinkType(model.path, v.path);
          const linkIndicator =
            linkType === "confirmed"
              ? "✅"
              : linkType === "assumed"
              ? "🔍"
              : "";

          return `
          <button
            class="version-tab ${idx === activeVersionIdx ? "active" : ""}"
            data-model-path="${this.escapeAttribute(model.path)}"
            data-version-idx="${idx}"
            title="${this.getLinkTypeTooltip(linkType, v.name)}"
            style="
              padding: 6px 10px;
              background: ${
                idx === activeVersionIdx
                  ? "linear-gradient(135deg, #bd93f9, #ff79c6)"
                  : "rgba(68, 71, 90, 0.6)"
              };
              border: ${
                idx === activeVersionIdx ? "none" : "1px solid #6272a4"
              };
              border-radius: 6px;
              color: #f8f8f2;
              font-size: 11px;
              font-weight: 600;
              cursor: pointer;
              transition: all 0.2s ease;
              display: flex;
              align-items: center;
              gap: 4px;
              white-space: nowrap;
            "
          >
            ${
              linkIndicator
                ? `<span style="font-size: 9px;">${linkIndicator}</span>`
                : ""
            }
            ${v.favorite ? '<span style="font-size: 10px;">⭐</span>' : ""}
            ${this.escapeHtml(v.name || "Version " + (idx + 1))}
          </button>
        `;
        })
        .join("")}
    </div>
    <button class="carousel-nav-btn carousel-nav-next" data-carousel-id="${carouselId}" title="Next version">
      ›
    </button>
  </div>
</div>
`;
    }

    // Get appropriate media for active version
    const appropriateMedia = this.getAppropriateMedia(activeVersion);
    let mediaHtml;

    if (appropriateMedia) {
      mediaHtml = this.renderMediaElement(appropriateMedia, activeVersion.name);
    } else {
      const icon = this.getModelTypeIcon(activeVersion.modelType);
      mediaHtml = `<div class="model-placeholder">${icon}</div>`;
    }

    // Wrap media in container with z-index control
    const mediaContainer = `
    <div style="position: relative; z-index: 1; overflow: hidden; border-radius: 0;">
      ${mediaHtml}
    </div>
  `;

    // Drop indicator for drag-drop
    const dropIndicator = `<div class="drop-indicator">📁</div>`;

    card.innerHTML = `
    ${dropIndicator}
    ${versionSelector}
    ${missingBadge}
    ${mismatchBadge}
    ${hashMismatchBadge}
    ${newVersionBadge}
    ${missingLinkBadge}
    ${mediaContainer}
    <div class="model-info">
      <div class="model-header">
        <div class="model-name">${this.escapeHtml(
          activeVersion.name || "Unnamed Model"
        )}</div>
        <div class="favorite-icon" onclick="event.stopPropagation(); app.toggleFavorite('${this.escapeAttribute(
          activeVersion.path
        )}')">
          ${activeVersion.favorite ? "⭐" : "☆"}
        </div>
      </div>
      <div class="model-meta">
        <div class="model-type">${activeVersion.modelType || "Unknown"}</div>
        ${
          activeVersion.baseModel
            ? `<div class="model-base">${activeVersion.baseModel}</div>`
            : ""
        }
      </div>
    </div>
  `;

    // Add version tab click handlers
    card.querySelectorAll(".version-tab").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const primaryPath = btn.dataset.modelPath; // This references the primary model path
        const versionIdx = parseInt(btn.dataset.versionIdx);
        this.setActiveVersion(primaryPath, versionIdx);
      });
    });

    // Add carousel navigation handlers for next/prev version selection
    const carouselScroll = card.querySelector(".version-carousel-scroll");
    if (carouselScroll) {
      const prevBtn = card.querySelector(".carousel-nav-prev");
      const nextBtn = card.querySelector(".carousel-nav-next");
      const versionTabs = Array.from(card.querySelectorAll(".version-tab"));

      const updateArrowStates = () => {
        const activeIdx = versionTabs.findIndex((tab) =>
          tab.classList.contains("active")
        );
        if (prevBtn && nextBtn) {
          prevBtn.classList.toggle("disabled", activeIdx <= 0);
          nextBtn.classList.toggle(
            "disabled",
            activeIdx >= versionTabs.length - 1
          );
        }
      };

      if (prevBtn) {
        prevBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          const activeIdx = versionTabs.findIndex((tab) =>
            tab.classList.contains("active")
          );
          if (activeIdx > 0) {
            versionTabs[activeIdx - 1].click();
          }
        });
      }

      if (nextBtn) {
        nextBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          const activeIdx = versionTabs.findIndex((tab) =>
            tab.classList.contains("active")
          );
          if (activeIdx < versionTabs.length - 1) {
            versionTabs[activeIdx + 1].click();
          }
        });
      }

      // Initial arrow state
      setTimeout(updateArrowStates, 0);
    }

    card.addEventListener("click", () => {
      this.selectModel(activeVersion);
    });

    wrapper.appendChild(card);
    return wrapper;
  }

  selectModel(model) {
    // Try to find which primary model this version belongs to
    let primaryPath = null;
    let versionIdx = -1;

    // First, check if this model itself is a primary model
    if (this.modelData.models[model.path]) {
      const checkModel = this.modelData.models[model.path];
      if (
        !checkModel.relatedVersions ||
        checkModel.relatedVersions.length === 0 ||
        this.isPrimaryVersion({ path: model.path, ...checkModel })
      ) {
        primaryPath = model.path;
        versionIdx = 0;
      }
    }

    // If not found, search through all models to find which one lists this as a related version
    if (primaryPath === null) {
      for (const [path, dbModel] of Object.entries(this.modelData.models)) {
        if (
          dbModel.relatedVersions &&
          dbModel.relatedVersions.includes(model.path)
        ) {
          // Check if this is the primary model
          if (this.isPrimaryVersion({ path, ...dbModel })) {
            primaryPath = path;
            const modelWithPath = { path: primaryPath, ...dbModel };
            const versions = this.getAllVersions(modelWithPath);
            versionIdx = versions.findIndex((v) => v.path === model.path);
            break;
          }
        }
      }
    }

    // If we found the primary model and version index, use setActiveVersion
    if (primaryPath && versionIdx >= 0) {
      this.setActiveVersion(primaryPath, versionIdx);
    } else {
      // Fallback: direct selection
      this.selectedModel = model;
      this.renderModelGrid();
      this.renderDetails(model);
    }
  }

  renderDetails(model) {
    const sidebar = document.getElementById("detailsSidebar");
    const mediaArray = model.exampleImages || [];

    // BUGFIX #3: Add delete button for missing models
    const deleteButton =
      model._status === "missing"
        ? `<button class="btn btn-danger" onclick="app.deleteMissingModel('${this.escapeAttribute(
            model.path
          )}')">🗑️ Delete</button>`
        : "";

    // BUGFIX #4: Show mismatch warning if needed
    const mismatchWarning = model._hasMismatch
      ? `
      <div class="missing-warning" style="border-color: #8be9fd; background: linear-gradient(135deg, rgba(139, 233, 253, 0.15), rgba(139, 233, 253, 0.05));">
        <div class="warning-header" style="color: #8be9fd;">⚠️ Type/Base Mismatch Detected</div>
        <p>This model has type or base model values that don't match the standard options:</p>
        ${
          model._typeMismatch
            ? `<p><strong>Type:</strong> "${model.modelType}" is not a standard type</p>`
            : ""
        }
        ${
          model._baseMismatch
            ? `<p><strong>Base:</strong> "${model.baseModel}" is not a standard base model</p>`
            : ""
        }
        <p style="margin-top: 12px; font-size: 12px; color: #6272a4;">You may want to edit this model to use standard values for better filtering.</p>
      </div>
    `
      : "";

    // 🆕 NEW: Hash mismatch warning (if detected)
    const hashMismatchWarning = model.hashMismatch?.detected
      ? `
  <div class="missing-warning" style="border-color: #ff5555; background: linear-gradient(135deg, rgba(255, 85, 85, 0.15), rgba(255, 85, 85, 0.05));">
    <div class="warning-header" style="color: #ff5555;">🚨 Hash Mismatch Detected!</div>
    <p>The file hash <strong>does not match</strong> the CivitAI version URL you assigned.</p>
    <p><strong>This means you likely downloaded a different version than the URL indicates.</strong></p>
    
    <div style="margin: 16px 0;">
      <div style="font-size: 12px; color: #6272a4; margin-bottom: 4px;">Local File Hash:</div>
      <div class="last-seen-path">${model.hashMismatch.localHash}</div>
      
      <div style="font-size: 12px; color: #6272a4; margin: 8px 0 4px 0;">Expected Hash (from CivitAI):</div>
      <div class="last-seen-path">${model.hashMismatch.expectedHash}</div>
    </div>
    
    <p style="font-size: 12px; color: #ff5555;"><strong>Action Required:</strong></p>
    <ul style="font-size: 12px; margin-left: 20px; line-height: 1.8;">
      <li>Check which version you actually downloaded</li>
      <li>Update the CivitAI URL to match your downloaded version, OR</li>
      <li>Download the correct version from the URL you assigned</li>
    </ul>
  </div>
`
      : "";

    // 🆕 NEW VERSION AVAILABLE WARNING
    const newVersionWarning = model.newVersionAvailable?.hasNewerVersion
      ? `
  <div class="missing-warning" style="border-color: #bd93f9; background: linear-gradient(135deg, rgba(189, 147, 249, 0.15), rgba(189, 147, 249, 0.05));">
    <div class="warning-header" style="color: #bd93f9;">✨ New Version Available!</div>
    <p><strong>A newer version of this model has been released on CivitAI!</strong></p>
    
    <div style="margin: 16px 0; padding: 12px; background: rgba(68, 71, 90, 0.3); border-radius: 8px;">
      <div style="font-size: 13px; font-weight: 600; color: #bd93f9; margin-bottom: 8px;">
        📦 ${this.escapeHtml(
          model.newVersionAvailable.newestVersion.versionName
        )}
      </div>
      <div style="font-size: 12px; color: #6272a4; margin-bottom: 4px;">
        📅 Published: ${new Date(
          model.newVersionAvailable.newestVersion.publishedAt
        ).toLocaleDateString()}
      </div>
      ${
        model.newVersionAvailable.newestVersion.baseModel
          ? `<div style="font-size: 12px; color: #6272a4;">
             🎯 Base: ${this.escapeHtml(
               model.newVersionAvailable.newestVersion.baseModel
             )}
           </div>`
          : ""
      }
    </div>
    
    ${
      model.newVersionAvailable.count > 1
        ? `<p style="font-size: 12px; color: #8be9fd; margin-bottom: 12px;">
           💡 There are ${model.newVersionAvailable.count} newer versions available in total.
         </p>`
        : ""
    }
    
    <div style="display: flex; gap: 8px; margin-top: 12px;">
      <a href="${
        model.civitaiUrl
      }" target="_blank" class="btn btn-primary" style="font-size: 12px; padding: 8px 16px;">
        🌐 View on CivitAI
      </a>
      ${
        model.civitaiModelId &&
        model.newVersionAvailable.newestVersion.versionId
          ? `<a href="https://civitai.com/models/${model.civitaiModelId}?modelVersionId=${model.newVersionAvailable.newestVersion.versionId}" 
             target="_blank" 
             class="btn btn-secondary" 
             style="font-size: 12px; padding: 8px 16px;">
            ⬇️ Download Latest
          </a>`
          : ""
      }
    </div>
  </div>
`
      : "";

    sidebar.innerHTML = `
  <div class="details-content">
    ${hashMismatchWarning}
    ${mismatchWarning}
    ...
  </div>
`;

    sidebar.innerHTML = `
            <div class="details-content">
                ${hashMismatchWarning}
                ${newVersionWarning}
                ${mismatchWarning}
                <div class="details-header">
                    <div class="details-title">${this.escapeHtml(
                      model.name || "Unnamed Model"
                    )}</div>
                    <div class="details-actions">
                        <button class="btn btn-primary" onclick="app.openEditModal()">✏️ Edit</button>
                        ${deleteButton}
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

                <!-- File Info -->
                <div class="section">
                  <div class="section-header">
                    <div class="section-title">📁 File Info</div>
                  </div>
                  <div class="info-grid">
                    <div class="info-item">
                      <span class="info-label">File Size</span>
                      <span class="info-value">${
                        model.fileSizeFormatted || "Unknown"
                      }</span>
                    </div>
                    ${
                      model.fileHash
                        ? `
                    <div class="info-item">
                      <span class="info-label">File Hash</span>
                      <span class="info-value" style="font-size: 12px; font-family: monospace; display: flex; align-items: center; gap: 8px;">
                        ${model.fileHash}
                        <a href="https://civarchive.com/sha256/${model.fileHash}" 
                          target="_blank" 
                          title="Search on CivArchive"
                          style="color: #8be9fd; text-decoration: none; font-size: 14px; transition: color 0.2s ease;"
                          onmouseover="this.style.color='#50fa7b'"
                          onmouseout="this.style.color='#8be9fd'">
                          🔗
                        </a>
                      </span>
                    </div>
                    `
                        : ""
                    }
                    ${
                      model.civitaiVersionId
                        ? `
                    <div class="info-item">
                      <span class="info-label">CivitAI Version</span>
                      <span class="info-value">${model.civitaiVersionId}</span>
                    </div>
                    `
                        : ""
                    }
                  </div>
                </div>

<!-- Versions Section -->
${
  model.civitaiData?.availableVersions &&
  model.civitaiData.availableVersions.length > 0
    ? `
<div class="section">
  <div class="section-header">
    <div class="section-title">📦 Available Versions</div>
  </div>
  <div class="version-list">
    ${model.civitaiData.availableVersions
      .map((version) => {
        let badge = "";
        let actions = "";

        if (version.status === "owned") {
          badge = '<span class="version-badge owned">✅ Installed</span>';
        } else if (version.status === "available") {
          badge = '<span class="version-badge available">🆕 Available</span>';
          actions = `
          <button class="btn-mini" onclick="window.open('https://civitai.com/models/${
            model.civitaiModelId
          }?modelVersionId=${
            version.versionId
          }', '_blank')">⬇️ Download</button>
          <button class="btn-mini" onclick="app.skipVersion('${this.escapeAttribute(
            model.path
          )}', '${version.versionId}')">⏭️ Skip</button>
        `;
        } else if (version.status === "skipped") {
          badge = '<span class="version-badge skipped">⏭️ Skipped</span>';
          actions = `
          <button class="btn-mini" onclick="app.unskipVersion('${this.escapeAttribute(
            model.path
          )}', '${version.versionId}')">↩️ Unskip</button>
        `;
        }

        return `
        <div class="version-item">
          <div class="version-info">
            <span class="version-name">${this.escapeHtml(
              version.name || "Unknown"
            )}</span>
            <span class="version-base">${version.baseModel || "Unknown"}</span>
            ${badge}
          </div>
          <div class="version-actions">
            ${actions}
          </div>
        </div>
      `;
      })
      .join("")}
  </div>
</div>
`
    : ""
}

<!-- Related Versions & Links -->
${
  model.relatedVersions && model.relatedVersions.length > 0
    ? `
<div class="section">
  <div class="section-header">
    <div class="section-title">🔗 Related Versions</div>
  </div>
  <div class="version-link-list">
    ${model.relatedVersions
      .map((relPath) => {
        const relModel = this.modelData.models[relPath];
        if (!relModel) return "";

        const linkMeta = model.linkMetadata?.[relPath] || {};
        const linkType = linkMeta.type || "unknown";
        const isConfirmed = linkType === "confirmed";
        const isAssumed = linkType === "assumed";

        return `
        <div class="version-link-item ${linkType}" 
          data-rel-path="${this.escapeAttribute(relPath)}"
          style="
          padding: 12px;
          background: rgba(68, 71, 90, 0.3);
          border-left: 3px solid ${
            isConfirmed ? "#50fa7b" : isAssumed ? "#8be9fd" : "#6272a4"
          };
          border-radius: 6px;
          margin-bottom: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
        ">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 16px;">${
              isConfirmed ? "✅" : isAssumed ? "🔍" : "🔗"
            }</span>
            <span style="font-weight: 600; color: #f8f8f2; font-size: 13px;">
              ${this.escapeHtml(relModel.name)}
            </span>
          </div>
          <div style="font-size: 11px; color: #8be9fd; margin-left: 24px;">
            ${relModel.baseModel || "Unknown"}
          </div>
          <div style="font-size: 11px; color: #6272a4; margin-left: 24px; margin-top: 4px;">
            ${
              isConfirmed
                ? "✅ Confirmed link (both have CivitAI data)"
                : isAssumed
                ? `🔍 Assumed link (matched by file size: ${linkMeta.sizeDiff?.toFixed(
                    2
                  )}% diff)`
                : "🔗 Linked"
            }
          </div>
          ${
            isAssumed
              ? `
            <div style="font-size: 11px; color: #ffb86c; margin-left: 24px; margin-top: 4px;">
              💡 Add CivitAI link to confirm this relationship
            </div>
          `
              : ""
          }
          ${
            linkMeta.versionName
              ? `
            <div style="font-size: 11px; color: #bd93f9; margin-left: 24px; margin-top: 4px;">
              CivitAI Version: ${this.escapeHtml(linkMeta.versionName)}
            </div>
          `
              : ""
          }
        </div>
      `;
      })
      .join("")}
  </div>
</div>
`
    : ""
}
                <!-- Tags -->
                ${
                  Array.isArray(model.tags) && model.tags.length > 0
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
                  Array.isArray(model.triggerWords) &&
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
                  Array.isArray(model.examplePrompts) &&
                  model.examplePrompts.length > 0
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
                  mediaArray && mediaArray.length > 0
                    ? `
                <div class="section">
                    <div class="section-header">
                        <div class="section-title">🖼️ Example Images</div>
                    </div>
                    <div class="image-gallery">
                        ${mediaArray
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

    // Add event listeners for related version items
    setTimeout(() => {
      const versionLinkItems = sidebar.querySelectorAll(
        ".version-link-item[data-rel-path]"
      );
      versionLinkItems.forEach((item) => {
        item.addEventListener("click", () => {
          const relPath = item.dataset.relPath;
          const relModel = this.modelData.models[relPath];
          if (relModel) {
            this.selectModel({ path: relPath, ...relModel });
          }
        });
      });
    }, 0);
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

    const fieldsByType = {
      checkpoint: ["resolution", "sampler", "steps", "cfg", "clipSkip"],
      lora: ["weight", "resolution", "steps", "cfg"],
      controlnet: ["preprocessor", "weight", "guidanceStart", "guidanceEnd"],
      upscaler: ["scale", "tileSize"],
      vae: [],
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
                        <option value="clip" ${
                          model.modelType === "clip" ? "selected" : ""
                        }>CLIP</option>
                        <option value="ipadapter" ${
                          model.modelType === "ipadapter" ? "selected" : ""
                        }>IP-Adapter</option>
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
                    )}" placeholder="e.g., SD 1.5, SDXL 1.0, Flux">
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
                    <input type="text" class="form-input" name="tags" value="${
                      Array.isArray(model.tags) ? model.tags.join(", ") : ""
                    }" placeholder="realistic, portrait, anime">
                </div>

                <div class="form-group">
                    <label class="form-label">Trigger Words (comma-separated)</label>
                    <input type="text" class="form-input" name="triggerWords" value="${
                      Array.isArray(model.triggerWords)
                        ? model.triggerWords.filter((w) => w !== "").join(", ")
                        : ""
                    }" placeholder="detailed, intricate">
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
                        ${
                          Array.isArray(model.examplePrompts)
                            ? model.examplePrompts
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
                                .join("")
                            : ""
                        }
                    </div>
                    <button type="button" class="btn-add" onclick="app.addPrompt()">+ Add Prompt</button>
                </div>

                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="app.closeEditModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">💾 Save Changes</button>
                </div>
            </form>
        `;

    // Form submit handler - bind this context properly
    const self = this;
    document.getElementById("editForm").addEventListener("submit", (e) => {
      e.preventDefault();
      self.saveModelEdits();
    });

    modal.style.display = "flex";
  }

  async saveModelEdits() {
    const form = document.getElementById("editForm");
    const formData = new FormData(form);

    // Get the model from modelData
    const model = this.modelData.models[this.selectedModel.path];

    // Store old URL to detect changes
    const oldUrl = model.civitaiUrl || "";

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

    // Update recommended settings
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

    // Save to server (which will auto-scrape if URL changed)
    try {
      const response = await fetch(
        `/api/models/${encodeURIComponent(this.selectedModel.path)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(model),
        }
      );

      if (response.ok) {
        const result = await response.json();

        // Check if scraping happened
        if (result.versionLinking) {
          const linking = result.versionLinking;
          let message = "✅ Model saved & CivitAI data fetched!";

          if (linking.stats.confirmed > 0) {
            message += `\n✅ ${linking.stats.confirmed} confirmed version link(s)`;
          }
          if (linking.stats.assumed > 0) {
            message += `\n🔍 ${linking.stats.assumed} assumed version link(s)`;
          }

          if (autoFilled.tags && autoFilled.tags.length > 0) {
            message += `\n📋 Auto-filled ${autoFilled.tags.length} tags`;
          }
          if (autoFilled.triggerWords && autoFilled.triggerWords.length > 0) {
            message += `\n✨ Auto-filled ${autoFilled.triggerWords.length} trigger words`;
          }

          this.showToast(message);
        } else {
          // Original message if no linking
          this.showToast("✅ Model saved");
        }

        // Reload activity log
        await this.loadActivityLog();

        // Reload to get updated data
        await this.loadFromServer();

        // Update view
        this.processModels();
        this.applyFilters();
        this.renderDetails(this.selectedModel);
        this.closeEditModal();
      }
    } catch (error) {
      console.error("Failed to save model:", error);
      this.showToast("❌ Failed to save model");
    }
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

  isPrimaryVersion(model) {
    /**
     * Determine if this model is the "primary" in its version group
     * Returns true if this model should be rendered, false if it should be hidden
     *
     * Primary selection rules (in order):
     * 1. 🆕 Newest published date (most recent version)
     * 2. Model with most relatedVersions (the hub)
     * 3. Model with civitaiUrl (confirmed linking)
     * 4. Alphabetically first path
     */

    // If no related versions, it's always primary
    if (!model.relatedVersions || model.relatedVersions.length === 0) {
      return true;
    }

    // Get all models in this version group (including self)
    const versionGroup = [model.path];
    model.relatedVersions.forEach((relPath) => {
      if (!versionGroup.includes(relPath)) {
        versionGroup.push(relPath);
      }
    });

    // 🆕 RULE 1: Find the newest model by published date
    let primaryPath = model.path;
    let newestDate = this.getModelPublishedDate(model);

    versionGroup.forEach((path) => {
      if (path === model.path) return; // Skip self

      const otherModel = this.modelData.models[path];
      if (!otherModel) return;

      const otherDate = this.getModelPublishedDate(otherModel);

      // If the other model is newer, it becomes primary
      if (
        otherDate &&
        (!newestDate || new Date(otherDate) > new Date(newestDate))
      ) {
        primaryPath = path;
        newestDate = otherDate;
      }
    });

    // If we found a model with a date, use it
    if (newestDate) {
      return primaryPath === model.path;
    }

    // FALLBACK: Use old logic if no dates are available
    let maxRelated = model.relatedVersions.length;

    versionGroup.forEach((path) => {
      if (path === model.path) return; // Skip self

      const otherModel = this.modelData.models[path];
      if (!otherModel) return;

      const otherRelatedCount = (otherModel.relatedVersions || []).length;

      // Rule 1: Most related versions
      if (otherRelatedCount > maxRelated) {
        primaryPath = path;
        maxRelated = otherRelatedCount;
      } else if (otherRelatedCount === maxRelated) {
        // Rule 2: Has CivitAI URL (tie-breaker)
        if (
          otherModel.civitaiUrl &&
          !this.modelData.models[primaryPath].civitaiUrl
        ) {
          primaryPath = path;
        } else if (
          (otherModel.civitaiUrl &&
            this.modelData.models[primaryPath].civitaiUrl) ||
          (!otherModel.civitaiUrl &&
            !this.modelData.models[primaryPath].civitaiUrl)
        ) {
          // Rule 3: Alphabetically first (final tie-breaker)
          if (path < primaryPath) {
            primaryPath = path;
          }
        }
      }
    });

    // This model is primary only if it's the one we selected
    return model.path === primaryPath;
  }

  /**
   * 🆕 Get the published date for a model
   * Checks multiple sources in order of priority:
   * 1. CivitAI version data (most accurate)
   * 2. CivitAI scraped data versions
   * 3. File modification date (last resort)
   */
  getModelPublishedDate(model) {
    // Priority 1: Check if the model has CivitAI data with version info
    if (model.civitaiData && model.civitaiData.versions) {
      // Find the version that matches this model's versionId
      const versionId = model.civitaiVersionId;
      if (versionId) {
        const version = model.civitaiData.versions.find(
          (v) => v.id === versionId
        );
        if (version && (version.publishedAt || version.createdAt)) {
          return version.publishedAt || version.createdAt;
        }
      }

      // If no specific version found, try to get the most recent date from any version
      for (const version of model.civitaiData.versions) {
        if (version.publishedAt || version.createdAt) {
          return version.publishedAt || version.createdAt;
        }
      }
    }

    // Priority 2: Check file modification date (fallback)
    // This would require the database to store file modification dates
    // For now, return null if no CivitAI date is available
    return null;
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

        // BUGFIX #2: Explicit re-process and re-filter
        this.processModels();
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

    let model = this.selectedModel;
    let actualModelPath = this.selectedModel?.path;
    if (modelPath) {
      model = this.modelData.models[modelPath];
      actualModelPath = modelPath;
    }

    const mediaArray = model?.exampleImages || [];

    if (!model || !mediaArray || mediaArray.length === 0) {
      console.error("Model or images not found");
      return;
    }

    const mediaItem = mediaArray.find((img) => img.filename === imagePath);

    if (!mediaItem) {
      console.error("Media item not found:", imagePath);
      return;
    }

    // Render media
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
        await this.loadFromServer();

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

        await this.loadFromServer();

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

  async skipVersion(modelPath, versionId) {
    try {
      const response = await fetch(
        `/api/models/${encodeURIComponent(modelPath)}/skip-version`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ versionId }),
        }
      );

      if (response.ok) {
        this.showToast("⏭️ Version skipped");
        await this.loadFromServer();

        if (this.selectedModel?.path === modelPath) {
          this.selectedModel = this.modelData.models[modelPath];
          this.renderDetails(this.selectedModel);
        }
      }
    } catch (error) {
      console.error("Failed to skip version:", error);
      this.showToast("❌ Failed to skip version");
    }
  }

  async unskipVersion(modelPath, versionId) {
    try {
      const response = await fetch(
        `/api/models/${encodeURIComponent(modelPath)}/unskip-version`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ versionId }),
        }
      );

      if (response.ok) {
        this.showToast("↩️ Version unskipped");
        await this.loadFromServer();

        if (this.selectedModel?.path === modelPath) {
          this.selectedModel = this.modelData.models[modelPath];
          this.renderDetails(this.selectedModel);
        }
      }
    } catch (error) {
      console.error("Failed to unskip version:", error);
      this.showToast("❌ Failed to unskip version");
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

    uploadStep.style.display = "block";
    previewStep.style.display = "none";
    confirmBtn.style.display = "none";

    this.pendingMerge = null;
    modal.style.display = "flex";

    if (!this.importDragDropSetup) {
      this.setupImportDragDrop();
      this.importDragDropSetup = true;
    }
  }

  closeImportModal() {
    document.getElementById("importModal").style.display = "none";
    this.pendingMerge = null;

    const fileInput = document.getElementById("importFileInput");
    if (fileInput) fileInput.value = "";
  }

  setupImportDragDrop() {
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("importFileInput");

    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

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

    dropZone.addEventListener("drop", (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        this.handleImportFile(files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        this.handleImportFile(e.target.files[0]);
      }
    });

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

      const dropZone = document.getElementById("dropZone");
      dropZone.classList.add("loading");

      const fileContent = await file.text();
      const newDb = JSON.parse(fileContent);

      dropZone.classList.remove("loading");

      if (!newDb.models || typeof newDb.models !== "object") {
        this.showToast("❌ Invalid database format - missing models object");
        return;
      }

      console.log(
        "✅ Loaded new database:",
        Object.keys(newDb.models).length,
        "models"
      );

      const mergeResult = this.analyzeMerge(this.modelData, newDb);

      console.log("📊 Merge analysis complete:", mergeResult.stats);

      this.pendingMerge = {
        newDb: newDb,
        analysis: mergeResult,
      };

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

    const oldByHash = new Map();
    const oldPaths = new Set();

    Object.entries(oldDb.models || {}).forEach(([path, model]) => {
      if (path.startsWith("_missing/")) {
        console.log(
          `⏭️  Skipping already-missing entry during analysis: ${path}`
        );
        return;
      }

      oldPaths.add(path);

      if (model.fileHash) {
        if (!oldByHash.has(model.fileHash)) {
          oldByHash.set(model.fileHash, []);
        }
        oldByHash.get(model.fileHash).push({ path, model });
      }

      if (model.variants) {
        if (model.variants.highHash) {
          if (!oldByHash.has(model.variants.highHash)) {
            oldByHash.set(model.variants.highHash, []);
          }
          oldByHash.get(model.variants.highHash).push({ path, model });
        }
        if (model.variants.lowHash) {
          if (!oldByHash.has(model.variants.lowHash)) {
            oldByHash.set(model.variants.lowHash, []);
          }
          oldByHash.get(model.variants.lowHash).push({ path, model });
        }
      }
    });

    console.log(
      "📚 Old database:",
      oldPaths.size,
      "non-missing models indexed"
    );

    const processedOldPaths = new Set();

    // 🔧 BUGFIX: Track which hash entries have been used
    const usedHashIndices = new Map(); // hash -> Set of used indices

    Object.entries(newDb.models || {}).forEach(([newPath, newModel]) => {
      const hash = newModel.fileHash;

      if (!hash) {
        console.warn("⚠️ New model without hash:", newPath);
        return;
      }

      let matched = false;

      if (oldByHash.has(hash)) {
        const matches = oldByHash.get(hash);

        // 🔧 BUGFIX: Try exact path match first (for duplicates)
        let matchIdx = matches.findIndex((m) => m.path === newPath);

        // If no exact match, find first unused match
        if (matchIdx === -1) {
          if (!usedHashIndices.has(hash)) {
            usedHashIndices.set(hash, new Set());
          }
          const usedIndices = usedHashIndices.get(hash);

          matchIdx = matches.findIndex((m, idx) => !usedIndices.has(idx));
        }

        if (matchIdx !== -1) {
          const match = matches[matchIdx];
          const { path: oldPath, model: oldModel } = match;

          // Mark this match as used
          if (!usedHashIndices.has(hash)) {
            usedHashIndices.set(hash, new Set());
          }
          usedHashIndices.get(hash).add(matchIdx);

          result.matched.push({
            hash,
            oldPath,
            newPath,
            name: newModel.name || oldModel.name || "Unnamed",
            pathChanged: oldPath !== newPath,
          });
          result.stats.matched++;
          processedOldPaths.add(oldPath);
          matched = true;
        }
      }

      // Try variant matching if main match failed
      if (!matched && newModel.variants) {
        if (
          newModel.variants.highHash &&
          oldByHash.has(newModel.variants.highHash)
        ) {
          const matches = oldByHash.get(newModel.variants.highHash);

          let matchIdx = matches.findIndex((m) => m.path === newPath);

          if (matchIdx === -1) {
            if (!usedHashIndices.has(newModel.variants.highHash)) {
              usedHashIndices.set(newModel.variants.highHash, new Set());
            }
            const usedIndices = usedHashIndices.get(newModel.variants.highHash);
            matchIdx = matches.findIndex((m, idx) => !usedIndices.has(idx));
          }

          if (matchIdx !== -1) {
            const match = matches[matchIdx];
            const { path: oldPath, model: oldModel } = match;

            if (!usedHashIndices.has(newModel.variants.highHash)) {
              usedHashIndices.set(newModel.variants.highHash, new Set());
            }
            usedHashIndices.get(newModel.variants.highHash).add(matchIdx);

            result.matched.push({
              hash: newModel.variants.highHash,
              oldPath,
              newPath,
              name: newModel.name || oldModel.name || "Unnamed",
              pathChanged: oldPath !== newPath,
              matchedViaVariant: true,
            });
            result.stats.matched++;
            processedOldPaths.add(oldPath);
            matched = true;
          }
        } else if (
          newModel.variants.lowHash &&
          oldByHash.has(newModel.variants.lowHash)
        ) {
          const matches = oldByHash.get(newModel.variants.lowHash);

          let matchIdx = matches.findIndex((m) => m.path === newPath);

          if (matchIdx === -1) {
            if (!usedHashIndices.has(newModel.variants.lowHash)) {
              usedHashIndices.set(newModel.variants.lowHash, new Set());
            }
            const usedIndices = usedHashIndices.get(newModel.variants.lowHash);
            matchIdx = matches.findIndex((m, idx) => !usedIndices.has(idx));
          }

          if (matchIdx !== -1) {
            const match = matches[matchIdx];
            const { path: oldPath, model: oldModel } = match;

            if (!usedHashIndices.has(newModel.variants.lowHash)) {
              usedHashIndices.set(newModel.variants.lowHash, new Set());
            }
            usedHashIndices.get(newModel.variants.lowHash).add(matchIdx);

            result.matched.push({
              hash: newModel.variants.lowHash,
              oldPath,
              newPath,
              name: newModel.name || oldModel.name || "Unnamed",
              pathChanged: oldPath !== newPath,
              matchedViaVariant: true,
            });
            result.stats.matched++;
            processedOldPaths.add(oldPath);
            matched = true;
          }
        }
      }

      if (!matched) {
        result.new.push({
          hash,
          path: newPath,
          name: newModel.name || "Unnamed",
        });
        result.stats.new++;
      }
    });

    oldPaths.forEach((oldPath) => {
      if (!processedOldPaths.has(oldPath)) {
        const oldModel = oldDb.models[oldPath];
        result.missing.push({
          hash: oldModel.fileHash,
          path: oldPath,
          name: oldModel.name || "Unnamed",
        });
        result.stats.missing++;
      }
    });

    console.log("✅ Analysis complete:", result.stats);

    return result;
  }

  showMergePreview(analysis) {
    const uploadStep = document.getElementById("uploadStep");
    const previewStep = document.getElementById("previewStep");
    const confirmBtn = document.getElementById("confirmMergeBtn");

    uploadStep.style.display = "none";
    previewStep.style.display = "block";
    confirmBtn.style.display = "block";

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

    this.populateMergeList("matchedList", analysis.matched, "matched");
    this.populateMergeList("newList", analysis.new, "new");
    this.populateMergeList("missingList", analysis.missing, "missing");

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

      const response = await fetch("/api/models", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mergedDb),
      });

      if (!response.ok) {
        throw new Error("Failed to save merged database");
      }

      console.log("💾 Merge saved successfully");

      // Reset all scrape cooldowns so models can be scraped immediately
      await this.resetScrapeCooldowns();

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

    const oldByHash = new Map();

    // BUGFIX: Track which paths were already marked as missing
    const alreadyMissingPaths = new Set();

    Object.entries(oldDb.models || {}).forEach(([path, model]) => {
      // Track already-missing entries so we don't re-add them
      if (path.startsWith("_missing/")) {
        alreadyMissingPaths.add(path);
        alreadyMissingPaths.add(
          model._lastSeenPath || path.replace(/^_missing\//, "")
        );
        console.log(`📝 Tracking deleted missing model: ${path}`);
        return; // Don't index missing entries for matching
      }

      if (model.fileHash) {
        oldByHash.set(model.fileHash, { path, model });
      }
      if (model.variants) {
        if (model.variants.highHash) {
          oldByHash.set(model.variants.highHash, { path, model });
        }
        if (model.variants.lowHash) {
          oldByHash.set(model.variants.lowHash, { path, model });
        }
      }
    });

    // Process new models (matched and new)
    Object.entries(newDb.models).forEach(([newPath, newModel]) => {
      const hash = newModel.fileHash;

      if (!hash) {
        console.warn("⚠️ Skipping model without hash:", newPath);
        return;
      }

      let oldModel = null;

      // Try to match by hash first
      if (oldByHash.has(hash)) {
        oldModel = oldByHash.get(hash).model;
      } else if (newModel.variants) {
        if (
          newModel.variants.highHash &&
          oldByHash.has(newModel.variants.highHash)
        ) {
          oldModel = oldByHash.get(newModel.variants.highHash).model;
        } else if (
          newModel.variants.lowHash &&
          oldByHash.has(newModel.variants.lowHash)
        ) {
          oldModel = oldByHash.get(newModel.variants.lowHash).model;
        }
      }

      // Fallback: Try to match by path if hash matching failed
      if (!oldModel && oldDb.models[newPath]) {
        oldModel = oldDb.models[newPath];
        console.log("📍 Matched by path (hash mismatch):", newPath);
      }

      if (oldModel) {
        merged.models[newPath] = this.mergeModelData(oldModel, newModel);
        console.log("✅ Merged:", newPath);
      } else {
        merged.models[newPath] = newModel;
        console.log("➕ Added new:", newPath);
      }
    });

    // Process missing models - but ONLY if they weren't already missing
    analysis.missing.forEach((item) => {
      // BUGFIX: Skip if this was already marked as missing (user deleted it)
      if (
        alreadyMissingPaths.has(item.path) ||
        alreadyMissingPaths.has(`_missing/${item.path}`)
      ) {
        console.log(
          `⏭️  Skipping previously deleted missing model: ${item.path}`
        );
        return;
      }

      const oldModel = oldDb.models[item.path];
      if (oldModel) {
        const missingKey = `_missing/${item.path}`;
        merged.models[missingKey] = {
          ...oldModel,
          _status: "missing",
          _lastSeenPath: item.path,
        };
        console.log("⚠️ Newly marked as missing:", missingKey);
      }
    });

    console.log(
      `✅ Merge complete: ${Object.keys(merged.models).length} total models`
    );
    return merged;
  }

  mergeModelData(oldModel, newModel) {
    console.log("🔀 Merging model data...");

    const merged = {
      name: newModel.name,
      modelType: newModel.modelType,
      fileType: newModel.fileType,
      fileHash: newModel.fileHash,
      fileSize: newModel.fileSize || oldModel.fileSize || 0,
      fileSizeFormatted:
        newModel.fileSizeFormatted || oldModel.fileSizeFormatted || "",
    };

    if (newModel.variants) {
      merged.variants = newModel.variants;
    } else if (oldModel.variants) {
      merged.variants = oldModel.variants;
    }

    const userFields = [
      "baseModel",
      "nsfw",
      "tags",
      "triggerWords",
      "notes",
      "recommendedSettings",
      "examplePrompts",
      "exampleImages",
      "civitaiUrl",
      "huggingFaceUrl",
      "githubUrl",
      "otherUrl",
      "favorite",
    ];

    userFields.forEach((field) => {
      const oldValue = oldModel[field];
      const newValue = newModel[field];

      let oldHasData = false;

      if (Array.isArray(oldValue)) {
        oldHasData = oldValue.length > 0;
      } else if (typeof oldValue === "object" && oldValue !== null) {
        oldHasData = Object.keys(oldValue).length > 0;
      } else if (typeof oldValue === "boolean") {
        oldHasData = true;
      } else if (typeof oldValue === "string") {
        oldHasData = oldValue.trim() !== "";
      }

      if (oldHasData) {
        merged[field] = oldValue;
        console.log(`  ✅ Preserved ${field} from old model`);
      } else if (newValue !== undefined && newValue !== null) {
        let newHasData = false;

        if (Array.isArray(newValue)) {
          newHasData = newValue.length > 0;
        } else if (typeof newValue === "object" && newValue !== null) {
          newHasData = Object.keys(newValue).length > 0;
        } else if (typeof newValue === "boolean") {
          newHasData = true;
        } else if (typeof newValue === "string") {
          newHasData = newValue.trim() !== "";
        }

        if (newHasData) {
          merged[field] = newValue;
        } else {
          if (Array.isArray(oldValue)) {
            merged[field] = [];
          } else if (typeof oldValue === "object" && oldValue !== null) {
            merged[field] = {};
          } else if (typeof oldValue === "boolean") {
            merged[field] = false;
          } else if (typeof oldValue === "string") {
            merged[field] = "";
          }
        }
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

    // BUGFIX #2: Explicit re-process and re-filter
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
    const mediaArray = model.exampleImages || [];

    if (mediaArray.length === 0) {
      return "pg";
    }

    const hasPgImage = mediaArray.some((img) => {
      const rating = img.rating || "pg";
      return rating === "pg";
    });
    const hasRImage = mediaArray.some((img) => img.rating === "r");
    const hasXImage = mediaArray.some((img) => img.rating === "x");

    if (hasPgImage) return "pg";
    if (hasRImage) return "r";
    if (hasXImage) return "x";
    return "pg";
  }

  canShowModel(model) {
    const currentRatingValue = this.getRatingValue(this.contentRating);

    let mediaArray = model.exampleImages;
    if (!mediaArray || typeof mediaArray !== "object") {
      mediaArray = [];
    } else if (!Array.isArray(mediaArray)) {
      mediaArray = Object.values(mediaArray).filter(
        (item) => item && typeof item === "object"
      );
    }

    if (mediaArray.length === 0) {
      if (model.nsfw) {
        return currentRatingValue >= this.getRatingValue("x");
      }
      return true;
    }

    const hasAppropriateImage = mediaArray.some((img) => {
      const imgRating = img.rating || (model.nsfw ? "x" : "pg");
      return this.getRatingValue(imgRating) <= currentRatingValue;
    });

    return hasAppropriateImage;
  }

  getAppropriateMedia(model) {
    if (!model.exampleImages) {
      return null;
    }

    let mediaArray = model.exampleImages;
    if (!Array.isArray(mediaArray)) {
      if (typeof mediaArray === "object") {
        mediaArray = Object.values(mediaArray).filter(
          (item) => item && typeof item === "object"
        );
      } else {
        mediaArray = [];
      }
    }

    if (mediaArray.length === 0) {
      return null;
    }

    const currentRatingValue = this.getRatingValue(this.contentRating);

    let appropriateMedia = mediaArray.filter((item) => {
      const itemRating = item.rating || "pg";
      return this.getRatingValue(itemRating) <= currentRatingValue;
    });

    if (appropriateMedia.length === 0) {
      return null;
    }

    if (!this.showVideos) {
      const imagesOnly = appropriateMedia.filter((item) => {
        const ext = (item.filename || "").toLowerCase();
        const isVideo = ext.endsWith(".mp4") || ext.endsWith(".webm");
        return !isVideo;
      });
      appropriateMedia = imagesOnly.length > 0 ? imagesOnly : appropriateMedia;
    }

    appropriateMedia.sort((a, b) => {
      const extA = (a.filename || "").toLowerCase();
      const extB = (b.filename || "").toLowerCase();
      const isVideoA = extA.endsWith(".mp4") || extA.endsWith(".webm");
      const isVideoB = extB.endsWith(".mp4") || extB.endsWith(".webm");

      if (this.showVideos) {
        if (isVideoA && !isVideoB) {
          return -1;
        }
        if (!isVideoA && isVideoB) {
          return 1;
        }
      }

      const ratingA = a.rating || "pg";
      const ratingB = b.rating || "pg";
      const valA = this.getRatingValue(ratingA);
      const valB = this.getRatingValue(ratingB);

      return valB - valA;
    });

    return appropriateMedia[0];
  }

  renderMediaElement(media, altText) {
    const filename = media.filename || "";
    const ext = filename.toLowerCase().split(".").pop();
    const isVideo = ext === "mp4" || ext === "webm";

    if (isVideo && this.showVideos) {
      const mimeType = ext === "mp4" ? "video/mp4" : "video/webm";
      const videoId = `video_${Math.random().toString(36).substr(2, 9)}`;

      return `
      <video 
        id="${videoId}"
        class="model-media" 
        autoplay 
        loop 
        muted 
        playsinline
        preload="auto"
        onended="this.currentTime = 0; this.play();"
        onerror="console.error('❌ Video failed to load:', '${filename}'); this.style.display='none'; this.parentElement.innerHTML='<div class=\\'model-placeholder\\'>⚠️ Video Error</div>';"
        onloadeddata="console.log('✅ Video loaded:', '${filename}'); this.play();"
      >
        <source src="images/${filename}" type="${mimeType}">
        Your browser does not support the video tag.
      </video>
    `;
    } else if (isVideo && !this.showVideos) {
      return `<div class="model-placeholder">🎬</div>`;
    } else {
      return `<img 
      src="images/${filename}" 
      alt="${altText}" 
      class="model-media"
      onerror="console.error('❌ Image failed to load:', '${filename}'); this.style.display='none'; this.parentElement.innerHTML='<div class=\\'model-placeholder\\'>⚠️ Image Error</div>';"
    >`;
    }
  }

  renderSettingsInputs(model) {
    const settings = model.recommendedSettings || {};
    const modelType = model.modelType || "checkpoint";

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
    // BUGFIX #8: Count ALL models including stacked versions
    // Total should be 271 (all unique models), not 208 (just primary versions)
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
      ipadapter: "🖼️",
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

    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      grid.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

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

    grid.addEventListener("drop", async (e) => {
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

      const formData = new FormData();
      formData.append("file", file);
      formData.append("modelPath", modelPath);

      const response = await fetch("/api/upload-media", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const result = await response.json();

      const rating = await this.promptForRating();
      if (!rating) {
        this.showToast("❌ Upload cancelled");
        return;
      }

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
        await this.loadFromServer();

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
