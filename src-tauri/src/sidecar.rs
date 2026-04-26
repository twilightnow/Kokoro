use std::{
    io::{Read, Write},
    net::TcpStream,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{LazyLock, Mutex},
    thread,
    time::Duration,
};

use tauri::{AppHandle, Runtime};
#[cfg(not(debug_assertions))]
use tauri::Manager;

static SIDECAR_CHILD: LazyLock<Mutex<Option<Child>>> = LazyLock::new(|| Mutex::new(None));

fn is_launchable_file(path: &Path) -> bool {
    path.metadata()
        .map(|metadata| metadata.is_file() && metadata.len() > 0)
        .unwrap_or(false)
}

fn health_ok() -> bool {
    let Ok(mut stream) = TcpStream::connect("127.0.0.1:18765") else {
        return false;
    };
    let request = "GET /health HTTP/1.1\r\nHost: 127.0.0.1:18765\r\nConnection: close\r\n\r\n";
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response.starts_with("HTTP/1.1 200") && response.contains("\"status\":\"ok\"")
}

fn flush_session() -> bool {
    let Ok(mut stream) = TcpStream::connect("127.0.0.1:18765") else {
        return false;
    };
    let request = concat!(
        "POST /admin/debug/flush-session HTTP/1.1\r\n",
        "Host: 127.0.0.1:18765\r\n",
        "Connection: close\r\n",
        "Content-Length: 0\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response.starts_with("HTTP/1.1 200")
}

fn project_root_from(start: &Path) -> Option<PathBuf> {
    for dir in start.ancestors() {
        if dir.join("package.json").exists()
            && dir.join("src").join("api").join("server.py").exists()
        {
            return Some(dir.to_path_buf());
        }
    }
    None
}

fn project_root() -> Option<PathBuf> {
    std::env::current_dir()
        .ok()
        .and_then(|dir| project_root_from(&dir))
        .or_else(|| {
            std::env::current_exe()
                .ok()
                .and_then(|exe| exe.parent().map(Path::to_path_buf))
                .and_then(|dir| project_root_from(&dir))
        })
}

#[cfg(not(debug_assertions))]
fn resource_sidecar<R: Runtime>(app: &AppHandle<R>) -> Option<PathBuf> {
    let names = ["kokoro-sidecar.exe", "kokoro-sidecar"];
    let resource_dir = app.path().resource_dir().ok()?;
    for name in names {
        let candidate = resource_dir.join(name);
        if is_launchable_file(&candidate) {
            return Some(candidate);
        }
    }
    None
}

#[cfg(not(debug_assertions))]
fn bundled_sidecar<R: Runtime>(app: &AppHandle<R>) -> Option<PathBuf> {
    if let Ok(path) = std::env::var("KOKORO_SIDECAR_EXE") {
        let candidate = PathBuf::from(path);
        if is_launchable_file(&candidate) {
            return Some(candidate);
        }
    }

    if let Some(candidate) = resource_sidecar(app) {
        return Some(candidate);
    }

    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(Path::to_path_buf))?;
    let names = ["kokoro-sidecar.exe", "kokoro-sidecar"];
    for name in names {
        let candidate = exe_dir.join(name);
        if is_launchable_file(&candidate) {
            return Some(candidate);
        }
    }
    None
}

fn python_executable(root: &Path) -> PathBuf {
    let candidates = if cfg!(windows) {
        [
            root.join(".venv").join("Scripts").join("python.exe"),
            root.join("venv").join("Scripts").join("python.exe"),
        ]
    } else {
        [
            root.join(".venv").join("bin").join("python"),
            root.join("venv").join("bin").join("python"),
        ]
    };

    for candidate in candidates {
        if is_launchable_file(&candidate) {
            return candidate;
        }
    }

    PathBuf::from("python")
}

fn command_for_sidecar<R: Runtime>(app: &AppHandle<R>) -> Result<Command, String> {
    #[cfg(debug_assertions)]
    let _ = app;

    #[cfg(not(debug_assertions))]
    {
        if let Some(sidecar) = bundled_sidecar(app) {
            let mut cmd = Command::new(sidecar);
            cmd.arg("--prod");
            return Ok(cmd);
        }
    }

    let root = project_root().ok_or_else(|| "Kokoro project root not found".to_string())?;
    let python = python_executable(&root);
    let mut cmd = Command::new(python);
    cmd.current_dir(root).env("PYTHONUTF8", "1").args([
        "-X",
        "utf8",
        "-m",
        "src.api.server",
        "--prod",
    ]);
    Ok(cmd)
}

pub fn ensure_sidecar_started<R: Runtime>(app: &AppHandle<R>) -> Result<(), String> {
    if health_ok() {
        return Ok(());
    }

    let mut guard = SIDECAR_CHILD
        .lock()
        .map_err(|_| "sidecar process lock poisoned".to_string())?;
    if let Some(child) = guard.as_mut() {
        if child.try_wait().map_err(|e| e.to_string())?.is_none() {
            return Ok(());
        }
        *guard = None;
    }

    let mut cmd = command_for_sidecar(app)?;
    cmd.stdin(Stdio::null());

    #[cfg(debug_assertions)]
    {
        cmd.stdout(Stdio::inherit()).stderr(Stdio::inherit());
    }

    #[cfg(not(debug_assertions))]
    {
        cmd.stdout(Stdio::null()).stderr(Stdio::null());
    }

    #[cfg(all(windows, not(debug_assertions)))]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("failed to start sidecar: {e}"))?;
    thread::sleep(Duration::from_millis(300));
    if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
        return Err(format!("sidecar exited immediately with status {status}"));
    }
    *guard = Some(child);
    drop(guard);

    thread::spawn(|| {
        for _ in 0..40 {
            if health_ok() {
                break;
            }
            thread::sleep(Duration::from_millis(250));
        }
    });

    Ok(())
}

pub fn shutdown_sidecar() {
    let _ = flush_session();
    if let Ok(mut guard) = SIDECAR_CHILD.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}
