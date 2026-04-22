use serde::Serialize;
use tauri::{AppHandle, Manager, PhysicalPosition, Runtime};

use crate::tray::show_or_create_admin_window;

#[derive(Serialize)]
pub struct MonitorBounds {
    x: i32,
    y: i32,
    width: u32,
    height: u32,
}

#[derive(Serialize)]
pub struct WindowMetrics {
    width: u32,
    height: u32,
    monitor: MonitorBounds,
}

#[tauri::command]
pub fn set_passthrough<R: Runtime>(app: AppHandle<R>, enabled: bool) -> Result<(), String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    win.set_ignore_cursor_events(enabled)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_window_position<R: Runtime>(app: AppHandle<R>) -> Result<(i32, i32), String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    let pos = win.outer_position().map_err(|e| e.to_string())?;
    Ok((pos.x, pos.y))
}

#[tauri::command]
pub fn set_window_position<R: Runtime>(app: AppHandle<R>, x: i32, y: i32) -> Result<(), String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    win.set_position(PhysicalPosition::new(x, y))
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_window_monitor_bounds<R: Runtime>(app: AppHandle<R>) -> Result<MonitorBounds, String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;

    let pos = win.outer_position().map_err(|e| e.to_string())?;
    let size = win.outer_size().map_err(|e| e.to_string())?;
    let center = PhysicalPosition::new(
        pos.x + (size.width as i32 / 2),
        pos.y + (size.height as i32 / 2),
    );

    let monitor = win
        .monitor_from_point(center.x as f64, center.y as f64)
        .map_err(|e| e.to_string())?
        .or_else(|| win.current_monitor().ok().flatten())
        .or_else(|| win.primary_monitor().ok().flatten())
        .ok_or_else(|| "Monitor not found".to_string())?;

    let monitor_pos = monitor.position();
    let monitor_size = monitor.size();

    Ok(MonitorBounds {
        x: monitor_pos.x,
        y: monitor_pos.y,
        width: monitor_size.width,
        height: monitor_size.height,
    })
}

#[tauri::command]
pub fn get_window_metrics<R: Runtime>(app: AppHandle<R>) -> Result<WindowMetrics, String> {
    let win = app
        .get_webview_window("main")
        .ok_or_else(|| "Window not found".to_string())?;
    let size = win.outer_size().map_err(|e| e.to_string())?;
    let monitor = get_window_monitor_bounds(app)?;

    Ok(WindowMetrics {
        width: size.width,
        height: size.height,
        monitor,
    })
}

#[tauri::command]
pub fn open_admin_window<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    show_or_create_admin_window(&app);
    Ok(())
}
