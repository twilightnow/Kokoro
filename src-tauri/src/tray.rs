use std::sync::{Mutex, OnceLock};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    utils::config::Color,
    AppHandle, Manager, PhysicalPosition, Runtime, WebviewUrl, WebviewWindowBuilder,
};

use crate::diagnostics::report_client_log;

/// ウィンドウ作成の競合を防ぐロック
/// 素早い連打でも admin ウィンドウが複数作成されないよう守る
static ADMIN_CREATION_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

fn admin_window_url() -> Result<WebviewUrl, String> {
    Ok(WebviewUrl::App("admin.html".into()))
}

fn report_admin_step(event: &str, message: &str) {
    report_client_log("tauri-window", event, "info", message);
}

fn report_admin_error(event: &str, message: &str) {
    report_client_log("tauri-window", event, "error", message);
}

pub fn show_or_create_admin_window<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    report_client_log(
        "tauri-window",
        "admin-show-or-create-start",
        "info",
        "show_or_create_admin_window started",
    );
    // 既存ウィンドウがあれば前面表示して終了
    if let Some(window) = app.get_webview_window("admin") {
        report_admin_step(
            "admin-existing-window-found",
            "existing admin window found; attempting to show",
        );
        if let Err(e) = window.unminimize() {
            report_admin_error(
                "admin-existing-window-unminimize-error",
                &format!("failed to unminimize existing admin window: {e}"),
            );
        }
        if let Err(e) = window.show() {
            report_admin_error(
                "admin-existing-window-show-error",
                &format!("failed to show existing admin window: {e}"),
            );
            let _ = window.destroy();
        } else {
            if let Err(e) = window.center() {
                report_admin_error(
                    "admin-existing-window-center-error",
                    &format!("failed to center existing admin window: {e}"),
                );
            }
            if let Err(e) = window.set_focus() {
                report_admin_error(
                    "admin-existing-window-focus-error",
                    &format!("failed to focus existing admin window: {e}"),
                );
            }
            report_admin_step(
                "admin-existing-window-shown",
                "existing admin window shown and focused",
            );
            return Ok(());
        }
    }

    // ロックを取得して競合作成を防ぐ（素早い連打対策）
    let lock = ADMIN_CREATION_LOCK.get_or_init(|| Mutex::new(()));
    let _guard = lock.lock().unwrap_or_else(|e| e.into_inner());

    // ロック取得後に再確認（他スレッドが先に作成していた場合）
    if let Some(window) = app.get_webview_window("admin") {
        report_admin_step(
            "admin-existing-window-found-after-lock",
            "existing admin window found after creation lock; attempting to show",
        );
        if let Err(e) = window.unminimize() {
            report_admin_error(
                "admin-existing-window-unminimize-after-lock-error",
                &format!("failed to unminimize existing admin window after lock: {e}"),
            );
        }
        if let Err(e) = window.show() {
            report_admin_error(
                "admin-existing-window-show-after-lock-error",
                &format!("failed to show existing admin window after lock: {e}"),
            );
            let _ = window.destroy();
        } else {
            if let Err(e) = window.center() {
                report_admin_error(
                    "admin-existing-window-center-after-lock-error",
                    &format!("failed to center existing admin window after lock: {e}"),
                );
            }
            if let Err(e) = window.set_focus() {
                report_admin_error(
                    "admin-existing-window-focus-after-lock-error",
                    &format!("failed to focus existing admin window after lock: {e}"),
                );
            }
            report_admin_step(
                "admin-existing-window-shown-after-lock",
                "existing admin window shown after creation lock",
            );
            return Ok(());
        }
    }

    report_admin_step(
        "admin-new-window-build-start",
        "building a new admin window",
    );
    let mut builder = WebviewWindowBuilder::new(app, "admin", admin_window_url()?)
        .title("Kokoro Admin")
        .inner_size(1100.0, 760.0)
        .min_inner_size(900.0, 620.0)
        .resizable(true)
        .maximizable(true)
        .minimizable(true)
        .closable(true)
        .decorations(true)
        .transparent(false)
        .background_color(Color(245, 245, 245, 255));

    if let Some(icon) = app.default_window_icon().cloned() {
        builder = builder.icon(icon).map_err(|e| e.to_string())?;
    }

    let window = builder
        // NOTICE:
        // visible(false) で非表示のまま作成し、center/focus 後に show() する。
        // visible(true) のままだとコンテンツが読み込まれる前に白い状態のウィンドウが
        // 表示されてしまう（WebView2 の初期化タイミング問題）。
        .visible(false)
        .always_on_top(false)
        .skip_taskbar(false)
        .build()
        .map_err(|e| e.to_string())?;

    window.show().map_err(|e| e.to_string())?;
    window.center().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    report_client_log(
        "tauri-window",
        "admin-new-window-created",
        "info",
        "new admin window created, shown and focused",
    );
    Ok(())
}

fn center_main_window<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;
    let window_size = window.outer_size().map_err(|e| e.to_string())?;
    let monitor = window
        .current_monitor()
        .map_err(|e| e.to_string())?
        .or_else(|| window.primary_monitor().ok().flatten())
        .ok_or_else(|| "monitor not found".to_string())?;
    let monitor_pos = monitor.position();
    let monitor_size = monitor.size();
    let x = monitor_pos.x + ((monitor_size.width as i32 - window_size.width as i32) / 2);
    let y = monitor_pos.y + ((monitor_size.height as i32 - window_size.height as i32) / 2);

    window.show().map_err(|e| e.to_string())?;
    window
        .set_position(PhysicalPosition::new(x, y))
        .map_err(|e| e.to_string())?;
    let persist_position_script = format!(
        "localStorage.setItem('kokoro-window-position', JSON.stringify({{ x: {x}, y: {y} }}));"
    );
    let _ = window.eval(&persist_position_script);
    window.set_focus().map_err(|e| e.to_string())
}

fn handle_menu_event<R: Runtime>(app: &AppHandle<R>, id: &str) {
    match id {
        "admin" => {
            report_client_log(
                "tauri-tray",
                "admin-menu-click",
                "info",
                "tray admin menu item clicked",
            );
            if let Err(e) = show_or_create_admin_window(app) {
                report_client_log(
                    "tauri-tray",
                    "admin-menu-open-error",
                    "error",
                    &format!("failed to open admin window from tray: {e}"),
                );
                eprintln!("failed to open admin window: {e}");
            }
        }
        "quit" => {
            // NOTICE:
            // app.exit(0) は Tauri のイベントループを通じて終了を試みるが、
            // トレイメニューのイベントハンドラから呼ぶと Windows 環境で
            // ブロックされる場合がある。std::process::exit(0) で確実に終了する。
            std::process::exit(0);
        }
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
        "center-main" => {
            report_client_log(
                "tauri-tray",
                "center-main-menu-click",
                "info",
                "tray center main window menu item clicked",
            );
            if let Err(e) = center_main_window(app) {
                report_client_log(
                    "tauri-tray",
                    "center-main-error",
                    "error",
                    &format!("failed to center main window from tray: {e}"),
                );
                eprintln!("failed to center main window: {e}");
            }
        }
        _ => {}
    }
}

pub fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let admin_i = MenuItem::with_id(app, "admin", "管理界面", true, None::<&str>)?;
    let toggle_i = MenuItem::with_id(app, "toggle", "显示 / 隐藏", true, None::<&str>)?;
    let center_i = MenuItem::with_id(app, "center-main", "重置角色到屏幕中央", true, None::<&str>)?;
    let quit_i = MenuItem::with_id(app, "quit", "退出 Kokoro", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&admin_i, &toggle_i, &center_i, &quit_i])?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(|app, event| {
            handle_menu_event(app, event.id.as_ref());
        })
        .build(app)?;

    Ok(())
}
