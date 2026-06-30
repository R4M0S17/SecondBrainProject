mod launcher;

use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{
    image::Image,
    Manager,
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

#[tauri::command]
fn get_cerebro_key() -> Option<String> {
    std::env::var("CEREBRO_API_KEY").ok()
}

#[tauri::command]
async fn proxy_api_request(
    method: String,
    path: String,
    body: Option<String>,
    api_key: Option<String>,
) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(if path.contains("/api/engine/start") {
            200
        } else {
            30
        }))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {e}"))?;

    let url = format!("http://127.0.0.1:7842{}", path);
    let mut req = match method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "PATCH" => client.patch(&url),
        "DELETE" => client.delete(&url),
        m => return Err(format!("Unsupported method: {m}")),
    };

    if let Some(b) = &body {
        req = req.header("Content-Type", "application/json").body(b.clone());
    }
    if let Some(k) = &api_key {
        req = req.header("X-Cerebro-Key", k);
    }

    let resp = req.send().await.map_err(|e| format!("Request failed: {e}"))?;
    let status = resp.status();
    let text = resp.text().await.map_err(|e| format!("Read failed: {e}"))?;
    if status.is_success() {
        Ok(text)
    } else {
        Err(format!("{} {}: {}", method, status.as_u16(), text))
    }
}

#[tauri::command]
async fn start_cerebro_backend(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || launcher::run_desktop_backend(&app))
        .await
        .map_err(|e| format!("Backend launcher panicked: {e}"))?
}

#[tauri::command]
async fn start_cerebro_engine(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || launcher::run_desktop_engine(&app))
        .await
        .map_err(|e| format!("Engine launcher panicked: {e}"))?
}

#[tauri::command]
async fn restart_cerebro_services(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        launcher::run_desktop_launcher(&app)
    })
    .await
    .map_err(|e| format!("Launcher panicked: {e}"))?
}

#[tauri::command]
async fn stop_cerebro_services(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        launcher::run_desktop_stop(&app)
    })
    .await
    .map_err(|e| format!("Stop script panicked: {e}"))?
}

#[tauri::command]
async fn show_recording_overlay(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("recording-overlay") {
        win.show().map_err(|e| e.to_string())?;
        win.set_always_on_top(true).map_err(|e| e.to_string())?;

        #[cfg(target_os = "macos")]
        {
            use cocoa::appkit::{NSWindow, NSWindowCollectionBehavior};
            use cocoa::base::id;
            if let Ok(ns_win_ptr) = win.ns_window() {
                let ns_win = ns_win_ptr as id;
                unsafe {
                    let behavior = NSWindow::collectionBehavior(ns_win);
                    NSWindow::setCollectionBehavior_(
                        ns_win,
                        behavior
                            | NSWindowCollectionBehavior::NSWindowCollectionBehaviorCanJoinAllSpaces
                            | NSWindowCollectionBehavior::NSWindowCollectionBehaviorStationary,
                    );
                }
            }
        }
    }
    Ok(())
}

#[tauri::command]
async fn hide_recording_overlay(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("recording-overlay") {
        win.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn focus_main_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("main") {
        win.show().map_err(|e| e.to_string())?;
        win.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            get_cerebro_key,
            proxy_api_request,
            start_cerebro_backend,
            start_cerebro_engine,
            restart_cerebro_services,
            stop_cerebro_services,
            show_recording_overlay,
            hide_recording_overlay,
            focus_main_window
        ])
        .on_window_event({
            let is_closing = std::sync::Arc::new(AtomicBool::new(false));
            move |window, event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    if is_closing.swap(true, Ordering::Relaxed) {
                        return;
                    }
                    api.prevent_close();
                    let app = window.app_handle().clone();
                    let win = window.clone();
                    tauri::async_runtime::spawn(async move {
                        let _ = tauri::async_runtime::spawn_blocking(move || {
                            let _ = launcher::run_desktop_stop(&app);
                        })
                        .await;
                        let _ = win.close();
                    });
                }
            }
        })
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(err) = launcher::ensure_backend_on_startup(&app_handle).await {
                    eprintln!("[cerebro] Backend auto-start: {err}");
                }
            });

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

                // Apply "visible on all Spaces" to the overlay window
                if let Some(overlay) = app.get_webview_window("recording-overlay") {
                    let ov_win = overlay.ns_window().unwrap() as id;
                    unsafe {
                        let behavior = NSWindow::collectionBehavior(ov_win);
                        NSWindow::setCollectionBehavior_(
                            ov_win,
                            behavior
                                | NSWindowCollectionBehavior::NSWindowCollectionBehaviorCanJoinAllSpaces
                                | NSWindowCollectionBehavior::NSWindowCollectionBehaviorStationary,
                        );
                    }
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

            let tray_icon = Image::from_path(
                app.path().resource_dir().unwrap().join("icons/tray-icon.png"),
            )
            .unwrap_or_else(|_| app.default_window_icon().unwrap().clone());

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

            let _ = window.show();
            let _ = window.set_focus();

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
