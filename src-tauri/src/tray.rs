use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    utils::config::Color,
    AppHandle, Manager, Runtime, WebviewUrl, WebviewWindowBuilder,
};

pub fn show_or_create_admin_window<R: Runtime>(app: &AppHandle<R>) {
    if let Some(window) = app.get_webview_window("admin") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.center();
        return;
    }

    let url = if cfg!(debug_assertions) {
        match "http://localhost:5173/admin.html".parse() {
            Ok(url) => WebviewUrl::External(url),
            Err(_) => return,
        }
    } else {
        WebviewUrl::App("admin.html".into())
    };

    if let Ok(window) = WebviewWindowBuilder::new(app, "admin", url)
        .title("Kokoro Admin")
        .inner_size(1100.0, 760.0)
        .min_inner_size(900.0, 620.0)
        .resizable(true)
        .maximizable(true)
        .minimizable(true)
        .closable(true)
        .decorations(true)
        .transparent(false)
        .background_color(Color(245, 245, 245, 255))
        .focused(true)
        .visible(true)
        .always_on_top(false)
        .skip_taskbar(false)
        .build()
    {
        let _ = window.center();
        let _ = window.set_focus();
    }
}

fn handle_menu_event<R: Runtime>(app: &AppHandle<R>, id: &str) {
    match id {
        "admin" => show_or_create_admin_window(app),
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
        _ => {}
    }
}

pub fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let admin_i = MenuItem::with_id(app, "admin", "管理界面", true, None::<&str>)?;
    let toggle_i = MenuItem::with_id(app, "toggle", "显示 / 隐藏", true, None::<&str>)?;
    let quit_i = MenuItem::with_id(app, "quit", "退出 Kokoro", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&admin_i, &toggle_i, &quit_i])?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(|app, event| {
            handle_menu_event(app, event.id.as_ref());
        })
        .build(app)?;

    Ok(())
}
