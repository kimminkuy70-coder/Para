//! Fixed packaged sidecar only. No shell plugin, user paths or executable args.
use serde_json::{json, Value};
use std::{io::{BufRead, BufReader, Read, Write}, process::{Command, Stdio},
    sync::{Arc, Mutex, atomic::AtomicU8, mpsc::{sync_channel, SyncSender}}, thread::JoinHandle};
use tauri::{ipc::Channel, Manager};

const MAX_FRAME: usize = 4 * 1024 * 1024;
type Writer = Arc<Mutex<Option<SyncSender<Vec<u8>>>>>;

pub struct Bridge { writer: Writer, waiter: JoinHandle<()> }
#[derive(Default)]
pub struct Desktop(pub Mutex<Option<Bridge>>, pub AtomicU8);

impl Desktop {
    pub fn take(&self) -> Option<Bridge> { self.0.lock().ok()?.take() }
}
impl Bridge {
    pub fn finish(self) {
        // Dropping the last sender closes stdin after queued frames. Python sees
        // EOF, cooperatively cancels, and finishes any active output transaction.
        if let Ok(mut writer) = self.writer.lock() { writer.take(); }
        let _ = self.waiter.join();
    }
}

#[tauri::command]
pub fn desktop_connect(app: tauri::AppHandle, state: tauri::State<'_, Desktop>,
    on_event: Channel<Value>) -> Result<(), String> {
    let mut slot = state.0.lock().map_err(|_| "engine_state")?;
    if slot.is_some() { return Err("engine_already_connected".into()); }
    let root = app.path().resource_dir().map_err(|_| "engine_resources")?.join("sidecar");
    let name = if cfg!(windows) { "Camtek_AOI_engine.exe" } else { "Camtek_AOI_engine" };
    let executable = root.join(name).canonicalize().map_err(|_| "engine_not_packaged")?;
    let canonical_root = root.canonicalize().map_err(|_| "engine_resources")?;
    if executable.parent() != Some(canonical_root.as_path()) || !executable.is_file() {
        return Err("engine_path_rejected".into());
    }
    let mut command = Command::new(executable);
    command.current_dir(canonical_root).stdin(Stdio::piped()).stdout(Stdio::piped())
        .stderr(Stdio::null()).env_remove("PYTHONPATH").env_remove("PYTHONHOME");
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let mut child = command.spawn().map_err(|_| "engine_start_failed")?;
    let mut input = child.stdin.take().ok_or("engine_stdin")?;
    let output = child.stdout.take().ok_or("engine_stdout")?;
    let (tx, rx) = sync_channel::<Vec<u8>>(8);
    let writer = Arc::new(Mutex::new(Some(tx)));
    let failure_writer = writer.clone();
    std::thread::spawn(move || {
        for bytes in rx {
            if input.write_all(&bytes).and_then(|_| input.flush()).is_err() { break; }
        }
    });
    std::thread::spawn(move || {
        let mut reader = BufReader::new(output);
        loop {
            let mut line = Vec::new();
            let read = reader.by_ref().take((MAX_FRAME + 1) as u64).read_until(b'\n', &mut line);
            if !matches!(read, Ok(n) if n > 0) { break; }
            if line.len() > MAX_FRAME { break; }
            match serde_json::from_slice::<Value>(&line) {
                Ok(event) if event["version"] == 1 => {
                    if on_event.send(event).is_err() { break; }
                }
                _ => break,
            }
        }
        if let Ok(mut writer) = failure_writer.lock() { writer.take(); }
        let _ = on_event.send(json!({"version":1,"id":null,"event":"error","code":"engine_closed"}));
    });
    let waiter = std::thread::spawn(move || { let _ = child.wait(); });
    *slot = Some(Bridge { writer, waiter });
    Ok(())
}

#[tauri::command]
pub fn desktop_send(request: Value, state: tauri::State<'_, Desktop>) -> Result<(), String> {
    const METHODS: [&str; 18] = ["contract", "configuration", "investigate", "analyze", "table_page", "cancel", "release", "shutdown", "recipe_open", "recipe_page", "recipe_edit", "document_open", "document_page", "document_edit", "commonality_catalog", "commonality_compare", "commonality_page", "commonality_export"];
    if request["version"] != 1 || !request["id"].as_u64().is_some_and(|n| n > 0 && n <= 9007199254740991)
        || !request["method"].as_str().is_some_and(|m| METHODS.contains(&m))
        || !request["params"].is_object() || request.as_object().map(|o| o.len()) != Some(4) {
        return Err("request_rejected".into());
    }
    let mut bytes = serde_json::to_vec(&request).map_err(|_| "request_encoding")?;
    bytes.push(b'\n');
    if bytes.len() > MAX_FRAME { return Err("request_too_large".into()); }
    let slot = state.0.lock().map_err(|_| "engine_state")?;
    let bridge = slot.as_ref().ok_or("engine_not_connected")?;
    let writer = bridge.writer.lock().map_err(|_| "engine_state")?;
    writer.as_ref().ok_or("engine_closed")?.try_send(bytes).map_err(|_| "engine_busy_or_closed".into())
}
