#[tauri::command]
fn app_contract_version() -> &'static str { "1" }

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![app_contract_version])
        .run(tauri::generate_context!())
        .expect("failed to run Camtek AOI Manager");
}
