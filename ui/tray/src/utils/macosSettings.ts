const MACOS_ACCESSIBILITY_URL =
  "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility";

export async function openAccessibilitySettings(): Promise<void> {
  try {
    const { open } = await import("@tauri-apps/plugin-shell");
    await open(MACOS_ACCESSIBILITY_URL);
  } catch {
    window.alert(
      `Open System Settings → Privacy & Security → Accessibility.\n\nOr run in Terminal:\nopen '${MACOS_ACCESSIBILITY_URL}'`,
    );
  }
}
