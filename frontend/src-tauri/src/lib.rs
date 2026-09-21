#[tauri::command]
fn app_contract_version() -> &'static str { "1" }

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(desktop::Desktop::default())
        .invoke_handler(tauri::generate_handler![app_contract_version, desktop::desktop_connect, desktop::desktop_send])
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
