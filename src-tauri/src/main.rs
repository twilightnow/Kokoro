// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod diagnostics;
mod sidecar;
mod tray;

fn main() {
    tauri::Builder::default()
        .on_window_event(|window, event| {
            if window.label() == "admin" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();
                    crate::diagnostics::report_client_log(
                        "tauri-window",
                        "admin-close-request-hidden",
                        "info",
                        "admin close request was converted to hide",
                    );
                }
            }
        })
        .setup(|app| {
            if let Err(error) = sidecar::ensure_sidecar_started(app.handle()) {
                diagnostics::report_client_log(
                    "tauri-sidecar",
                    "sidecar-start-failed",
                    "error",
                    &error,
                );
            }
            tray::setup_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::set_passthrough,
            commands::set_main_always_on_top,
            commands::get_window_position,
            commands::set_window_position,
            commands::set_main_window_size,
            commands::get_window_monitor_bounds,
            commands::get_window_metrics,
            commands::open_admin_window,
            commands::close_admin_window,
            commands::set_admin_always_on_top,
            commands::set_start_on_boot,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app, event| {
            if let tauri::RunEvent::Exit = event {
                sidecar::shutdown_sidecar();
            }
        });
}
