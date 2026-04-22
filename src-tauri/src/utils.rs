use std::path::PathBuf;

/// 返回项目根目录下的 characters/ 目录路径。
/// dev 模式下 CWD 是 src-tauri/，需要向上一级。
pub fn characters_dir() -> PathBuf {
    let base = std::env::current_dir().unwrap_or_default();
    // src-tauri/ 下运行时，../characters 才是项目根目录的角色文件夹
    let candidate = base.join("../characters");
    if candidate.exists() {
        return candidate;
    }
    // 打包后 CWD 与可执行文件同级，直接用 characters/
    base.join("characters")
}

/// characters/ 目录下所有子目录名（即可用角色名）。
pub fn read_character_names() -> Vec<String> {
    let dir = characters_dir();
    if !dir.exists() {
        return vec![];
    }
    let mut names: Vec<String> = std::fs::read_dir(&dir)
        .map(|entries| {
            entries
                .filter_map(|e| e.ok())
                .filter(|e| e.path().is_dir())
                .filter(|e| e.path().join("personality.yaml").exists())
                .filter_map(|e| e.file_name().into_string().ok())
                .collect()
        })
        .unwrap_or_default();
    names.sort();
    names
}
