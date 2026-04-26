use std::path::Path;

fn main() {
    println!("cargo:rerun-if-changed=icons/icon.ico");
    println!("cargo:rerun-if-changed=icons/icon.icns");
    println!("cargo:rerun-if-changed=icons/32x32.png");
    println!("cargo:rerun-if-changed=icons/128x128.png");
    println!("cargo:rerun-if-changed=icons/128x128@2x.png");

    let sidecar_resource = Path::new("../dist/kokoro-sidecar.exe");
    if !sidecar_resource.exists() {
        if let Some(parent) = sidecar_resource.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let _ = std::fs::write(sidecar_resource, []);
    }

    tauri_build::build()
}
