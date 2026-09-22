#[tauri::command]
fn app_contract_version() -> &'static str { "1" }

/// Open the OS folder chooser and return the selected absolute path, or null if
/// the user cancels. The path is the user's explicit Explorer-style choice — the
/// same trust model as the tkinter program — and the Python engine validates it
/// before persisting. No arbitrary path is injectable from the web layer.
#[tauri::command]
fn pick_folder() -> Option<String> {
    rfd::FileDialog::new()
        .pick_folder()
        .and_then(|path| path.to_str().map(str::to_string))
}

/// Quit the app so a staged self-update can swap the install folder. Goes
/// through ExitRequested below, which lets the engine finish cleanly first.
#[tauri::command]
fn app_exit(app: tauri::AppHandle) { app.exit(0); }

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(desktop::Desktop::default())
        .invoke_handler(tauri::generate_handler![app_contract_version, pick_folder, app_exit, desktop::desktop_connect, desktop::desktop_send])
        .build(tauri::generate_context!())
        .expect("failed to build Camtek AOI Manager")
        .run(|app, event| {
            if let tauri::RunEvent::ExitRequested { api, .. } = event {
                use std::sync::atomic::Ordering;
                let state = app.state::<desktop::Desktop>();
                if state.1.load(Ordering::SeqCst) == 1 { api.prevent_exit(); return; }
                if let Some(bridge) = app.state::<desktop::Desktop>().take() {
                    state.1.store(1, Ordering::SeqCst);
                    api.prevent_exit();
                    let handle = app.clone();
                    std::thread::spawn(move || {
                        bridge.finish();
                        handle.state::<desktop::Desktop>().1.store(2, Ordering::SeqCst);
                        handle.exit(0);
                    });
                }
            }
        });
}
mod desktop;
use tauri::Manager;
