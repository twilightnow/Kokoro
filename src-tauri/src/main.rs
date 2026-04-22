// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod tray;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            tray::setup_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::set_passthrough,
            commands::get_window_position,
            commands::set_window_position,
            commands::get_window_monitor_bounds,
            commands::get_window_metrics,
            commands::open_admin_window,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
