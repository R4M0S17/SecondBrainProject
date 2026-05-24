//! Runs desktop launcher/stop scripts before or from the UI.

use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Deserialize;
use tauri::Manager;

#[derive(Debug, Deserialize)]
struct DesktopConfig {
    cerebro_root: String,
}

fn desktop_config_path() -> PathBuf {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/"))
        .join(".cerebro")
        .join("desktop.json")
}

fn read_cerebro_root(config_path: &Path) -> Result<PathBuf, String> {
    let raw = std::fs::read_to_string(config_path)
        .map_err(|e| format!("Could not read {}: {e}", config_path.display()))?;
    let cfg: DesktopConfig = serde_json::from_str(&raw)
        .map_err(|e| format!("Invalid {}: {e}", config_path.display()))?;
    if cfg.cerebro_root.trim().is_empty() {
        return Err("desktop.json: cerebro_root is empty".into());
    }
    Ok(PathBuf::from(cfg.cerebro_root))
}

fn resolve_script<R: tauri::Runtime, M: Manager<R>>(
    manager: &M,
    script_name: &str,
) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        let config_path = desktop_config_path();
        if !config_path.is_file() {
            return Err(format!(
                "Missing {}. From the cerebro folder run: make desktop-config",
                config_path.display()
            ));
        }
        let root = read_cerebro_root(&config_path)?;
        let script = root.join("scripts").join(script_name);
        if !script.is_file() {
            return Err(format!("Script not found: {}", script.display()));
        }
        return Ok(script);
    }

    // Prefer scripts from desktop.json cerebro_root (updated without reinstalling .app).
    let config_path = desktop_config_path();
    if config_path.is_file() {
        if let Ok(root) = read_cerebro_root(&config_path) {
            let script = root.join("scripts").join(script_name);
            if script.is_file() {
                return Ok(script);
            }
        }
    }

    let resource_dir = manager.path().resource_dir().map_err(|e| e.to_string())?;

    for candidate in [
        resource_dir.join(script_name),
        resource_dir.join("resources").join(script_name),
    ] {
        if candidate.is_file() {
            return Ok(candidate);
        }
    }

    let nested = resource_dir
        .join("_up_")
        .join("_up_")
        .join("scripts")
        .join(script_name);
    if nested.is_file() {
        return Ok(nested);
    }

    Err(format!(
        "{script_name} not found in app resources and no desktop.json fallback."
    ))
}

fn run_script<R: tauri::Runtime, M: Manager<R>>(
    manager: &M,
    script_name: &str,
    failure_label: &str,
) -> Result<(), String> {
    let script = resolve_script(manager, script_name)?;
    let output = Command::new("/bin/bash")
        .arg(&script)
        .output()
        .map_err(|e| format!("Failed to run {}: {e}", script.display()))?;

    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let detail = if !stderr.is_empty() {
        stderr
    } else if !stdout.is_empty() {
        stdout
    } else {
        format!(
            "{failure_label} exited with status {}. See ~/.cerebro/logs/",
            output.status.code().unwrap_or(-1)
        )
    };
    Err(detail)
}

pub fn run_desktop_launcher<R: tauri::Runtime, M: Manager<R>>(manager: &M) -> Result<(), String> {
    run_script(manager, "cerebro_desktop_launcher.sh", "Launcher")
}

pub fn run_desktop_stop<R: tauri::Runtime, M: Manager<R>>(manager: &M) -> Result<(), String> {
    run_script(manager, "cerebro_desktop_stop.sh", "Stop script")
}
