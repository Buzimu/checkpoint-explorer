/**
 * Notification Service - Toast notifications
 */
export class NotificationService {
  constructor() {
    this.container = this.createContainer();
  }

  createContainer() {
    const container = document.createElement("div");
    container.id = "notification-container";
    container.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 10000;
      pointer-events: none;
    `;
    document.body.appendChild(container);
    return container;
  }

  show(message, type = "info", duration = 3000) {
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      padding: 12px 20px;
      margin-bottom: 10px;
      border-radius: 6px;
      color: #f8f8f2;
      font-weight: 500;
      opacity: 0;
      transform: translateX(100%);
      transition: all 0.3s ease;
      pointer-events: auto;
      cursor: pointer;
      background-color: ${this.getColor(type)};
    `;

    this.container.appendChild(notification);

    // Animate in
    setTimeout(() => {
      notification.style.opacity = "1";
      notification.style.transform = "translateX(0)";
    }, 10);

    // Auto remove
    setTimeout(() => {
      this.remove(notification);
    }, duration);

    // Click to dismiss
    notification.addEventListener("click", () => {
      this.remove(notification);
    });
  }

  remove(notification) {
    notification.style.opacity = "0";
    notification.style.transform = "translateX(100%)";
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }

  getColor(type) {
    const colors = {
      success: "#50fa7b",
      error: "#ff5555",
      warning: "#ffb86c",
      info: "#8be9fd",
    };
    return colors[type] || colors.info;
  }

  success(message) {
    this.show(message, "success");
  }
  error(message) {
    this.show(message, "error");
  }
  warning(message) {
    this.show(message, "warning");
  }
  info(message) {
    this.show(message, "info");
  }
}
