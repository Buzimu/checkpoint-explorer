/**
 * Keyboard Service - Global keyboard shortcut management
 */
export class KeyboardService {
  constructor() {
    this.shortcuts = new Map();
    this.enabled = true;

    // Bind the handler
    this.handleKeydown = this.handleKeydown.bind(this);

    // Attach global listener
    document.addEventListener("keydown", this.handleKeydown);
  }

  register(shortcut, callback, options = {}) {
    const {
      preventDefault = true,
      stopPropagation = false,
      when = () => true, // Conditional function
    } = options;

    this.shortcuts.set(shortcut.toLowerCase(), {
      callback,
      preventDefault,
      stopPropagation,
      when,
    });
  }

  unregister(shortcut) {
    this.shortcuts.delete(shortcut.toLowerCase());
  }

  handleKeydown(event) {
    if (!this.enabled) return;

    // Don't handle shortcuts when typing in inputs (unless it's a global shortcut)
    const target = event.target;
    const isInput = ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);

    // Build shortcut string
    const parts = [];
    if (event.ctrlKey || event.metaKey) parts.push("ctrl");
    if (event.altKey) parts.push("alt");
    if (event.shiftKey) parts.push("shift");

    // Get the key
    let key = event.key.toLowerCase();

    // Normalize special keys
    const keyMap = {
      arrowup: "up",
      arrowdown: "down",
      arrowleft: "left",
      arrowright: "right",
      enter: "enter",
      escape: "esc",
      " ": "space",
    };

    key = keyMap[key] || key;

    // Skip single character shortcuts in inputs
    if (isInput && parts.length === 0 && key.length === 1) {
      return;
    }

    parts.push(key);
    const shortcut = parts.join("+");

    // Check if we have this shortcut
    const handler = this.shortcuts.get(shortcut);

    if (handler && handler.when()) {
      if (handler.preventDefault) {
        event.preventDefault();
      }

      if (handler.stopPropagation) {
        event.stopPropagation();
      }

      handler.callback(event);
    }
  }

  enable() {
    this.enabled = true;
  }

  disable() {
    this.enabled = false;
  }

  destroy() {
    document.removeEventListener("keydown", this.handleKeydown);
    this.shortcuts.clear();
  }
}
