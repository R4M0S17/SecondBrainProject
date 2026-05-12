use tauri::{
    image::Image,
    Manager,
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            // Enable true macOS full-screen via the green button
            #[cfg(target_os = "macos")]
            {
                use cocoa::appkit::{NSWindow, NSWindowCollectionBehavior};
                use cocoa::base::id;
                let ns_win = window.ns_window().unwrap() as id;
                unsafe {
                    let behavior = NSWindow::collectionBehavior(ns_win);
                    NSWindow::setCollectionBehavior_(
                        ns_win,
                        behavior | NSWindowCollectionBehavior::NSWindowCollectionBehaviorFullScreenPrimary,
                    );
                }
            }

            let win_shortcut = window.clone();
            let shortcut = Shortcut::new(
                Some(Modifiers::SUPER | Modifiers::SHIFT),
                Code::Space,
            );
            app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, _event| {
                if win_shortcut.is_visible().unwrap_or(false) {
                    let _ = win_shortcut.hide();
                } else {
                    let _ = win_shortcut.show();
                    let _ = win_shortcut.set_focus();
                }
            })?;

            // Ícono en la menubar → click izquierdo muestra/oculta la ventana
            let tray_icon = Image::from_path(
                app.path().resource_dir().unwrap().join("icons/tray-icon.png")
            ).unwrap_or_else(|_| app.default_window_icon().unwrap().clone());

            let _tray = TrayIconBuilder::new()
                .icon(tray_icon)
                .icon_as_template(true)
                .tooltip("Cerebro")
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("main") {
                            if win.is_visible().unwrap_or(false) {
                                let _ = win.hide();
                            } else {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Reopen { has_visible_windows, .. } = event {
                if !has_visible_windows {
                    if let Some(win) = app_handle.get_webview_window("main") {
                        let _ = win.show();
                        let _ = win.set_focus();
                    }
                }
            }
        });
}
