// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod tray;
mod utils;

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
            commands::get_characters,
            commands::switch_character,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
