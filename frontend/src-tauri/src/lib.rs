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

/// Tray residency (tkinter tray.py): while an automatic watch is on, closing the
/// window only hides it so the engine keeps watching. The tooltip says which
/// watches run and carries the latest notice.
#[derive(Default)]
struct Background(std::sync::Mutex<bool>);

const TRAY_ID: &str = "main";

#[tauri::command]
fn set_background(app: tauri::AppHandle, state: tauri::State<'_, Background>, enabled: bool, tooltip: String) {
    if let Ok(mut flag) = state.0.lock() { *flag = enabled; }
    if let Some(tray) = app.tray_by_id(TRAY_ID) {
        let text: String = tooltip.chars().take(120).collect();
        let _ = tray.set_tooltip(Some(if text.is_empty() { "Camtek AOI Manager".to_string() } else { text }));
        let _ = tray.set_visible(enabled);
    }
}

fn show_main(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(desktop::Desktop::default())
        .manage(Background::default())
        .setup(|app| {
            use tauri::menu::{Menu, MenuItem};
            use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
            let open = MenuItem::with_id(app, "open", "프로그램 열기", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "자동 감시 종료(프로그램 종료)", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &quit])?;
            let mut builder = TrayIconBuilder::with_id(TRAY_ID)
                .tooltip("Camtek AOI Manager")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show_main(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. }
                        | TrayIconEvent::DoubleClick { button: MouseButton::Left, .. } = event {
                        show_main(tray.app_handle());
                    }
                });
            if let Some(icon) = app.default_window_icon() { builder = builder.icon(icon.clone()); }
            let tray = builder.build(app)?;
            let _ = tray.set_visible(false);      // shown only while a watch keeps the app resident
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let resident = window.app_handle().state::<Background>().0.lock().map(|f| *f).unwrap_or(false);
                if resident {
                    // Keep the engine (and its watch scheduler) running; the tray brings it back.
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![app_contract_version, pick_folder, app_exit, set_background, desktop::desktop_connect, desktop::desktop_send])
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
