#[cfg(target_os = "windows")]
pub fn active_window_title() -> String {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GetForegroundWindow, GetWindowTextLengthW, GetWindowTextW,
    };

    unsafe {
        let window = GetForegroundWindow();
        if window.is_null() {
            return String::new();
        }
        let length = GetWindowTextLengthW(window);
        if length <= 0 {
            return String::new();
        }
        let mut buffer = vec![0u16; length as usize + 1];
        let copied = GetWindowTextW(window, buffer.as_mut_ptr(), buffer.len() as i32);
        if copied <= 0 {
            return String::new();
        }
        String::from_utf16_lossy(&buffer[..copied as usize])
    }
}

#[cfg(not(target_os = "windows"))]
pub fn active_window_title() -> String {
    String::new()
}
