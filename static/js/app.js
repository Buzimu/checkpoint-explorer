// Global state
let currentModel = null;
let allModels = [];
let pendingUpload = null;

// Initialize on page load
document.addEventListener("DOMContentLoaded", function () {
  // Store models from template
  allModels = Array.from(document.querySelectorAll(".model-item")).map(
    (item) => ({
      id: item.dataset.modelId,
      type: item.dataset.type,
      rating: item.dataset.rating,
      element: item,
    })
  );
});

// Model selection
function selectModel(modelId) {
  // Update active state in sidebar
  document.querySelectorAll(".model-item").forEach((item) => {
    item.classList.remove("active");
    if (item.dataset.modelId === modelId) {
      item.classList.add("active");
    }
  });

  // Fetch and display model details
  fetch(`/api/model/${modelId}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        currentModel = data.model;
        displayModelDetails(data.model);
      }
    })
    .catch((error) => {
      console.error("Error fetching model:", error);
      showNotification("Error loading model details", "error");
    });
}

// Display model details
function displayModelDetails(model) {
  const mainContent = document.getElementById("main-content");

  // Build preview section
  const previewHTML = buildPreviewSection(model);

  // Build info section
  const infoHTML = buildInfoSection(model);

  // Build settings section
  const settingsHTML = buildSettingsSection(model);

  // Build links section
  const linksHTML = buildLinksSection(model);

  // Build notes section
  const notesHTML = buildNotesSection(model);

  mainContent.innerHTML = `
        <div class="model-detail">
            <div class="model-header">
                <div class="model-title-section">
                    <h2>${escapeHtml(model.name)}</h2>
                    <div class="model-meta">
                        <span>📦 ${model.type.toUpperCase()}</span>
                        <span>💾 ${model.size_formatted}</span>
                        <span>📅 ${new Date(
                          model.modified
                        ).toLocaleDateString()}</span>
                    </div>
                </div>
                <div class="model-actions">
                    <button onclick="openInExplorer('${escapeHtml(
                      model.path
                    )}')" class="btn-secondary">
                        📁 Open Folder
                    </button>
                    <button onclick="saveModelChanges()" class="btn-primary">
                        💾 Save Changes
                    </button>
                </div>
            </div>
            
            ${previewHTML}
            ${infoHTML}
            ${settingsHTML}
            ${linksHTML}
            ${notesHTML}
        </div>
    `;

  // Initialize drag and drop
  initializeDragDrop();
}

// Build preview section
function buildPreviewSection(model) {
  const hasImage = model.preview_image;
  const hasVideo = model.has_video && model.preview_video;

  return `
        <div class="preview-section">
            <div class="preview-header">
                <h3>Preview</h3>
                <div class="preview-controls">
                    <div class="rating-selector">
                        <label>Rating:</label>
                        <select class="rating-dropdown" onchange="updateModelRating('${
                          model.id
                        }', this.value)">
                            <option value="pg" ${
                              model.rating === "pg" ? "selected" : ""
                            }>👁️ PG - Safe</option>
                            <option value="r" ${
                              model.rating === "r" ? "selected" : ""
                            }>⚠️ R - Mature</option>
                            <option value="x" ${
                              model.rating === "x" ? "selected" : ""
                            }>🔞 X - Adult</option>
                        </select>
                    </div>
                    ${
                      hasVideo
                        ? `
                    <button class="toggle-btn" id="video-toggle" onclick="toggleVideo()">
                        <span class="icon">🎬</span>
                        <span>Video</span>
                    </button>
                    `
                        : ""
                    }
                </div>
            </div>
            
            <div class="preview-container" id="preview-container">
                ${
                  hasImage || hasVideo
                    ? `
                    <img id="preview-image" 
                         src="/static/previews/${
                           model.preview_image || model.preview_video
                         }" 
                         alt="${escapeHtml(model.name)}"
                         style="${
                           hasVideo ? "display: none;" : "display: block;"
                         }">
                    ${
                      hasVideo
                        ? `
                    <video id="preview-video" 
                           loop autoplay muted
                           src="/static/previews/${model.preview_video}"
                           style="display: block;">
                    </video>
                    `
                        : ""
                    }
                `
                    : `
                    <div class="no-preview">
                        <p>📸 No preview available</p>
                        <p style="margin-top: 0.5rem; font-size: 0.85rem;">Drag & drop an image or video here</p>
                    </div>
                `
                }
                <div class="drop-overlay" id="drop-overlay">
                    <div class="drop-message">
                        <span class="icon">📎</span>
                        <p>Drop image or video to associate</p>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Build info section
function buildInfoSection(model) {
  return `
        <div class="info-grid">
            <div class="info-card">
                <h3>Technical Information</h3>
                <div class="info-row">
                    <span class="info-label">Filename:</span>
                    <span class="info-value">${escapeHtml(
                      model.filename
                    )}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Type:</span>
                    <span class="info-value">${model.type.toUpperCase()}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Size:</span>
                    <span class="info-value">${model.size_formatted}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Modified:</span>
                    <span class="info-value">${new Date(
                      model.modified
                    ).toLocaleString()}</span>
                </div>
            </div>
            
            <div class="info-card">
                <h3>File Location</h3>
                <div class="info-row">
                    <span class="info-value" style="word-break: break-all; font-size: 0.85rem;">
                        ${escapeHtml(model.path)}
                    </span>
                </div>
            </div>
        </div>
    `;
}

// Build settings section
function buildSettingsSection(model) {
  const config = model.settings_config;
  let settingsHTML = "";

  config.fields.forEach((field) => {
    const fieldName = field
      .replace("_", " ")
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");

    const value = model.settings[field] || config.defaults[field];

    let inputHTML = "";

    if (field === "resolution") {
      inputHTML = `
                <select name="${field}" id="setting-${field}">
                    ${getResolutionOptions(value)}
                </select>
            `;
    } else if (field === "sampler") {
      inputHTML = `
                <select name="${field}" id="setting-${field}">
                    ${getSamplerOptions(value)}
                </select>
            `;
    } else if (
      field === "weight" ||
      field === "control_weight" ||
      field === "cfg_scale"
    ) {
      inputHTML = `
                <input type="number" step="0.1" min="0" max="2" 
                       name="${field}" id="setting-${field}" value="${value}">
            `;
    } else if (field === "steps" || field === "clip_skip") {
      inputHTML = `
                <input type="number" min="1" max="150" 
                       name="${field}" id="setting-${field}" value="${value}">
            `;
    } else {
      inputHTML = `
                <input type="text" name="${field}" id="setting-${field}" value="${escapeHtml(
        value
      )}">
            `;
    }

    settingsHTML += `
            <div class="setting-row">
                <label>${fieldName}:</label>
                ${inputHTML}
            </div>
        `;
  });

  return `
        <div class="settings-section">
            <h3>Recommended Settings</h3>
            ${settingsHTML}
        </div>
    `;
}

// Build links section
function buildLinksSection(model) {
  return `
        <div class="links-section">
            <h3>External Links</h3>
            
            <div class="link-item">
                <span class="link-icon">🎨</span>
                <input type="url" id="link-civitai" placeholder="CivitAI URL" 
                       value="${model.links.civitai || ""}">
                ${
                  model.links.civitai
                    ? `
                    <a href="${model.links.civitai}" target="_blank" class="visit-btn">Visit</a>
                `
                    : ""
                }
            </div>
            
            <div class="link-item">
                <span class="link-icon">🤗</span>
                <input type="url" id="link-huggingface" placeholder="Hugging Face URL"
                       value="${model.links.huggingface || ""}">
                ${
                  model.links.huggingface
                    ? `
                    <a href="${model.links.huggingface}" target="_blank" class="visit-btn">Visit</a>
                `
                    : ""
                }
            </div>
            
            <div class="link-item">
                <span class="link-icon">🐙</span>
                <input type="url" id="link-github" placeholder="GitHub URL"
                       value="${model.links.github || ""}">
                ${
                  model.links.github
                    ? `
                    <a href="${model.links.github}" target="_blank" class="visit-btn">Visit</a>
                `
                    : ""
                }
            </div>
            
            <div class="link-item">
                <span class="link-icon">🔗</span>
                <input type="url" id="link-custom" placeholder="Other URL"
                       value="${model.links.custom || ""}">
                ${
                  model.links.custom
                    ? `
                    <a href="${model.links.custom}" target="_blank" class="visit-btn">Visit</a>
                `
                    : ""
                }
            </div>
        </div>
    `;
}

// Build notes section
function buildNotesSection(model) {
  return `
        <div class="notes-section">
            <h3>Notes & Documentation</h3>
            <textarea class="notes-textarea" id="model-notes" 
                      placeholder="Add your notes, usage tips, or paste readme content here...">${escapeHtml(
                        model.notes || ""
                      )}</textarea>
        </div>
    `;
}

// Toggle video/image
function toggleVideo() {
  const img = document.getElementById("preview-image");
  const video = document.getElementById("preview-video");
  const btn = document.getElementById("video-toggle");

  if (!video) return;

  if (video.style.display === "none") {
    // Show video
    img.style.display = "none";
    video.style.display = "block";
    video.play();
    btn.classList.add("active");
  } else {
    // Show image
    video.style.display = "none";
    video.pause();
    img.style.display = "block";
    btn.classList.remove("active");
  }
}

// Update model rating
function updateModelRating(modelId, rating) {
  fetch("/api/update-rating", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_id: modelId, rating: rating }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showNotification("Rating updated", "success");
        // Update in sidebar
        const modelItem = document.querySelector(
          `[data-model-id="${modelId}"]`
        );
        if (modelItem) {
          modelItem.dataset.rating = rating;
        }
      }
    })
    .catch((error) => {
      console.error("Error updating rating:", error);
      showNotification("Error updating rating", "error");
    });
}

// Initialize drag and drop
function initializeDragDrop() {
  const container = document.getElementById("preview-container");
  const overlay = document.getElementById("drop-overlay");

  if (!container) return;

  container.addEventListener("dragover", (e) => {
    e.preventDefault();
    overlay.classList.add("active");
  });

  container.addEventListener("dragleave", (e) => {
    if (e.target === container) {
      overlay.classList.remove("active");
    }
  });

  container.addEventListener("drop", (e) => {
    e.preventDefault();
    overlay.classList.remove("active");

    const file = e.dataTransfer.files[0];
    if (!file) return;

    // Check if it's an image or video
    if (!file.type.match(/image.*|video.*/)) {
      showNotification("Please drop an image or video file", "error");
      return;
    }

    // Store pending upload
    pendingUpload = { modelId: currentModel.id, file };

    // Show rating dialog
    document.getElementById("rating-dialog").classList.add("active");
  });
}

// Confirm rating for upload
function confirmRating() {
  const rating = document.getElementById("preview-rating").value;

  if (!pendingUpload) return;

  // Create form data
  const formData = new FormData();
  formData.append("file", pendingUpload.file);
  formData.append("model_id", pendingUpload.modelId);
  formData.append("rating", rating);

  // Show uploading notification
  showNotification("Uploading preview...", "info");

  // Upload
  fetch("/api/upload-preview", {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showNotification("Preview uploaded successfully!", "success");
        // Reload model details
        selectModel(currentModel.id);
      } else {
        showNotification("Error uploading preview", "error");
      }
    })
    .catch((err) => {
      console.error(err);
      showNotification("Error uploading preview", "error");
    });

  cancelRating();
}

// Cancel rating dialog
function cancelRating() {
  document.getElementById("rating-dialog").classList.remove("active");
  pendingUpload = null;
}

// Save model changes
function saveModelChanges() {
  if (!currentModel) return;

  // Collect settings
  const settings = {};
  const config = currentModel.settings_config;
  config.fields.forEach((field) => {
    const input = document.getElementById(`setting-${field}`);
    if (input) {
      settings[field] = input.value;
    }
  });

  // Collect links
  const links = {
    civitai: document.getElementById("link-civitai")?.value || "",
    huggingface: document.getElementById("link-huggingface")?.value || "",
    github: document.getElementById("link-github")?.value || "",
    custom: document.getElementById("link-custom")?.value || "",
  };

  // Get notes
  const notes = document.getElementById("model-notes")?.value || "";

  // Update model
  fetch(`/api/model/${currentModel.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings, links, notes }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showNotification("Changes saved successfully!", "success");
        currentModel = data.model;
      } else {
        showNotification("Error saving changes", "error");
      }
    })
    .catch((error) => {
      console.error("Error saving:", error);
      showNotification("Error saving changes", "error");
    });
}

// Scan models
function scanModels() {
  const path = document.getElementById("models-path").value;

  if (!path) {
    showNotification("Please enter a models directory path", "error");
    return;
  }

  // Save path to settings
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ models_directory: path }),
  })
    .then(() => {
      showNotification("Scanning models...", "info");
      return fetch("/api/scan", { method: "POST" });
    })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showNotification(`Found ${data.count} models!`, "success");
        setTimeout(() => location.reload(), 1000);
      } else {
        showNotification("Error scanning models", "error");
      }
    })
    .catch((error) => {
      console.error("Error scanning:", error);
      showNotification("Error scanning models", "error");
    });
}

// Filter models
function filterModels() {
  const searchTerm = document
    .getElementById("search-input")
    .value.toLowerCase();
  const typeFilter = document.getElementById("type-filter").value;
  const ratingFilter = document.getElementById("rating-filter").value;

  let visibleCount = 0;

  allModels.forEach((model) => {
    let visible = true;

    // Search filter
    if (searchTerm) {
      const name = model.element
        .querySelector(".model-item-name")
        .textContent.toLowerCase();
      visible = visible && name.includes(searchTerm);
    }

    // Type filter
    if (typeFilter) {
      visible = visible && model.type === typeFilter;
    }

    // Rating filter
    if (ratingFilter) {
      visible = visible && model.rating === ratingFilter;
    }

    model.element.style.display = visible ? "flex" : "none";
    if (visible) visibleCount++;
  });

  // Update count
  document.getElementById("model-count").textContent = `${visibleCount} models`;
}

// Clear filters
function clearFilters() {
  document.getElementById("search-input").value = "";
  document.getElementById("type-filter").value = "";
  document.getElementById("rating-filter").value = "";
  filterModels();
}

// Open in file explorer (placeholder - would need electron for real implementation)
function openInExplorer(path) {
  showNotification("File explorer integration requires desktop app", "info");
  console.log("Open path:", path);
}

// Show notification
function showNotification(message, type = "info") {
  // Simple console notification for now
  // Could be enhanced with toast notifications
  console.log(`[${type.toUpperCase()}] ${message}`);

  // Update status bar temporarily
  const statusRight = document.querySelector(".status-right");
  const originalHTML = statusRight.innerHTML;

  const icons = {
    success: "✅",
    error: "❌",
    info: "ℹ️",
  };

  statusRight.innerHTML = `
        <span class="status-indicator">●</span>
        <span>${icons[type]} ${message}</span>
    `;

  setTimeout(() => {
    statusRight.innerHTML = originalHTML;
  }, 3000);
}

// Helper: Escape HTML
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Helper: Get resolution options
function getResolutionOptions(selected) {
  const options = [
    "512x512",
    "512x768",
    "768x512",
    "768x768",
    "768x1024",
    "1024x768",
    "1024x1024",
    "1024x1536",
    "1536x1024",
  ];

  return options
    .map(
      (opt) =>
        `<option value="${opt}" ${
          opt === selected ? "selected" : ""
        }>${opt}</option>`
    )
    .join("");
}

// Helper: Get sampler options
function getSamplerOptions(selected) {
  const options = [
    "DPM++ 2M Karras",
    "DPM++ SDE Karras",
    "Euler a",
    "Euler",
    "LMS",
    "Heun",
    "DPM2",
    "DPM2 a",
    "DPM++ 2S a",
    "DPM++ 2M",
    "DPM++ SDE",
    "DPM fast",
    "DPM adaptive",
    "LMS Karras",
    "DPM2 Karras",
    "DPM2 a Karras",
    "DPM++ 2S a Karras",
  ];

  return options
    .map(
      (opt) =>
        `<option value="${opt}" ${
          opt === selected ? "selected" : ""
        }>${opt}</option>`
    )
    .join("");
}
