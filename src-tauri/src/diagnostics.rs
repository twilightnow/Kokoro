use serde_json::json;
use std::{
    io::Write,
    net::TcpStream,
    time::{SystemTime, UNIX_EPOCH},
};

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or_default()
}

pub fn report_client_log(source: &str, event: &str, level: &str, message: &str) {
    let payload = json!({
        "source": source,
        "event": event,
        "level": level,
        "message": message,
        "details": {
            "origin": "tauri-rust",
            "timestamp_ms": now_ms()
        }
    })
    .to_string();

    let request = format!(
        "POST /admin/debug/client-log HTTP/1.1\r\n\
         Host: 127.0.0.1:18765\r\n\
         Content-Type: application/json\r\n\
         Content-Length: {}\r\n\
         Connection: close\r\n\r\n{}",
        payload.len(),
        payload
    );

    if let Ok(mut stream) = TcpStream::connect("127.0.0.1:18765") {
        let _ = stream.write_all(request.as_bytes());
        let _ = stream.flush();
    }
}
