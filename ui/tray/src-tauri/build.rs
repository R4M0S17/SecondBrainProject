use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let scripts_dir = manifest_dir.join("../../../scripts");
    let resources_dir = manifest_dir.join("resources");

    for name in ["cerebro_desktop_launcher.sh", "cerebro_desktop_stop.sh"] {
        let src = scripts_dir.join(name);
        let dst = resources_dir.join(name);
        if src.is_file() {
            fs::create_dir_all(&resources_dir).expect("create resources dir");
            fs::copy(&src, &dst).unwrap_or_else(|e| panic!("copy {name} for app bundle: {e}"));
        }
    }

    tauri_build::build()
}
