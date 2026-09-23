// GUI subsystem on Windows: no black console window next to the app. Closing
// that console used to kill the whole program (engine included). Applied to
// debug builds too, because test packages are sometimes built without --release.
// The Python engine is a console program but is started with CREATE_NO_WINDOW
// (desktop.rs), so it runs in the background without a window either.
#![windows_subsystem = "windows"]

fn main() { camtek_aoi_manager_lib::run(); }
