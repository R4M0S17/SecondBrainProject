mod launcher;

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
            stop_cerebro_services
        ])
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
