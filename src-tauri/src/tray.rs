use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, Runtime,
};
use crate::utils::read_character_names;

fn handle_menu_event<R: Runtime>(app: &AppHandle<R>, id: &str) {
    match id {
        "quit" => app.exit(0),
        "toggle" => {
            if let Some(window) = app.get_webview_window("main") {
                if window.is_visible().unwrap_or(false) {
                    let _ = window.hide();
                } else {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        }
        id if id.starts_with("char_") => {
            let char_name = &id["char_".len()..];
            let _ = app.emit("character-switch-requested", char_name.to_string());
        }
        _ => {}
    }
}

pub fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let toggle_i = MenuItem::with_id(app, "toggle", "显示 / 隐藏", true, None::<&str>)?;
    let quit_i = MenuItem::with_id(app, "quit", "退出 Kokoro", true, None::<&str>)?;

    let char_names = read_character_names();
    let char_items: Vec<MenuItem<R>> = char_names
        .iter()
        .map(|name| {
            MenuItem::with_id(
                app,
                format!("char_{name}"),
                name.as_str(),
                true,
                None::<&str>,
            )
        })
        .collect::<tauri::Result<Vec<_>>>()?;

    // 固定アイテム + キャラクターアイテムを結合
    let mut menu_refs: Vec<&dyn tauri::menu::IsMenuItem<R>> = vec![&toggle_i, &quit_i];
    for item in &char_items {
        menu_refs.push(item);
    }

    let menu = Menu::with_items(app, menu_refs.as_slice())?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(|app, event| {
            handle_menu_event(app, event.id.as_ref());
        })
        .build(app)?;

    Ok(())
}
