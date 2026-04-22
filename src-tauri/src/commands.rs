use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, Runtime};
use crate::utils::read_character_names;

/// 透明区域クリック透過を切り替える。
#[tauri::command]
pub fn set_passthrough<R: Runtime>(app: AppHandle<R>, enabled: bool) -> Result<(), String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    win.set_ignore_cursor_events(enabled)
        .map_err(|e| e.to_string())
}

/// 現在のウィンドウ外側位置（物理ピクセル）を返す。
#[tauri::command]
pub fn get_window_position<R: Runtime>(app: AppHandle<R>) -> Result<(i32, i32), String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    let pos = win.outer_position().map_err(|e| e.to_string())?;
    Ok((pos.x, pos.y))
}

/// ウィンドウを指定した物理ピクセル座標に移動する。
#[tauri::command]
pub fn set_window_position<R: Runtime>(app: AppHandle<R>, x: i32, y: i32) -> Result<(), String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    win.set_position(PhysicalPosition::new(x, y))
        .map_err(|e| e.to_string())
}

/// characters/ ディレクトリ内のキャラクター名一覧を返す。
#[tauri::command]
pub fn get_characters() -> Result<Vec<String>, String> {
    Ok(read_character_names())
}

/// キャラクター切替リクエストをフロントエンドにイベント通知する。
#[tauri::command]
pub fn switch_character<R: Runtime>(app: AppHandle<R>, name: String) -> Result<(), String> {
    app.emit("character-switch-requested", name)
        .map_err(|e| e.to_string())
}
