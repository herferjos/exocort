#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use base64::{engine::general_purpose::STANDARD as BASE64_STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, BufReader};
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::{
    collections::{HashMap, HashSet},
    fs,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant, UNIX_EPOCH},
};
use tauri::{menu::{Menu, MenuItem}, tray::TrayIconBuilder, AppHandle, Manager, State};

const UI_STATE_FILE: &str = ".exocort/ui.generated.yaml";
const TRAY_OPEN_ID: &str = "tray-open";
const TRAY_QUIT_ID: &str = "tray-quit";

fn frontend_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("frontend/src-tauri must have a parent directory")
        .to_path_buf()
}

fn repo_root() -> PathBuf {
    frontend_root()
        .parent()
        .expect("frontend must live inside the repository root")
        .to_path_buf()
}

fn backend_root() -> PathBuf {
    repo_root().join("backend")
}

fn services_root() -> PathBuf {
    repo_root().join("services")
}

fn repo_tmp_root() -> PathBuf {
    repo_root().join("tmp")
}

fn repo_vault_root() -> PathBuf {
    repo_root().join("vault")
}

fn ui_state_path() -> PathBuf {
    frontend_root().join(UI_STATE_FILE)
}

struct BackendState {
    child: Mutex<Option<Child>>,
    temp_config: Mutex<Option<PathBuf>>,
    logs: Arc<Mutex<BackendLogs>>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            temp_config: Mutex::new(None),
            logs: Arc::new(Mutex::new(BackendLogs::default())),
        }
    }
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct BackendLogEntry {
    seq: u64,
    stream: String,
    message: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendLogBatch {
    entries: Vec<BackendLogEntry>,
    next_seq: u64,
}

#[derive(Default)]
struct BackendLogs {
    entries: Vec<BackendLogEntry>,
    next_seq: u64,
}

#[derive(Serialize)]
struct BackendStatus {
    running: bool,
    pid: Option<u32>,
    message: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ConfigCatalog {
    configs: Vec<String>,
    active_config: String,
}

struct AppRuntimeState {
    exit_requested: Mutex<bool>,
}

#[cfg(target_os = "macos")]
#[link(name = "ApplicationServices", kind = "framework")]
extern "C" {
    fn CGPreflightScreenCaptureAccess() -> u8;
    fn CGRequestScreenCaptureAccess() -> u8;
}

#[cfg(target_os = "macos")]
#[link(name = "AVFoundation", kind = "framework")]
extern "C" {}

#[cfg(target_os = "macos")]
extern "C" {
    fn objc_getClass(name: *const std::ffi::c_char) -> *mut std::ffi::c_void;
    fn sel_registerName(name: *const std::ffi::c_char) -> *const std::ffi::c_void;
    fn objc_msgSend(
        receiver: *mut std::ffi::c_void,
        op: *const std::ffi::c_void,
    ) -> *mut std::ffi::c_void;
    fn dispatch_semaphore_create(value: std::ffi::c_long) -> *mut std::ffi::c_void;
    fn dispatch_semaphore_signal(dsema: *mut std::ffi::c_void) -> std::ffi::c_long;
    fn dispatch_semaphore_wait(dsema: *mut std::ffi::c_void, timeout: u64) -> std::ffi::c_long;
    static _NSConcreteStackBlock: std::ffi::c_void;
}

#[cfg(target_os = "macos")]
#[repr(C)]
struct MicBlockDescriptor {
    reserved: u64,
    size: u64,
}

#[cfg(target_os = "macos")]
#[repr(C)]
struct MicBlock {
    isa: *const std::ffi::c_void,
    flags: std::ffi::c_int,
    reserved: std::ffi::c_int,
    invoke: unsafe extern "C" fn(*mut MicBlock, bool),
    descriptor: *const MicBlockDescriptor,
    sema: *mut std::ffi::c_void,
}

#[cfg(target_os = "macos")]
unsafe impl Send for MicBlock {}

#[cfg(target_os = "macos")]
static MIC_BLOCK_DESCRIPTOR: MicBlockDescriptor = MicBlockDescriptor {
    reserved: 0,
    size: std::mem::size_of::<MicBlock>() as u64,
};

#[cfg(target_os = "macos")]
unsafe extern "C" fn mic_block_invoke(block: *mut MicBlock, _granted: bool) {
    dispatch_semaphore_signal((*block).sema);
}

#[cfg(target_os = "macos")]
fn microphone_auth_status() -> isize {
    use std::ffi::c_char;
    use std::ffi::c_void;
    unsafe {
        let nss = objc_getClass(b"NSString\0".as_ptr() as *const c_char);
        let str_sel = sel_registerName(b"stringWithUTF8String:\0".as_ptr() as *const c_char);
        type MkStr = unsafe extern "C" fn(*mut c_void, *const c_void, *const c_char) -> *mut c_void;
        let mk_str: MkStr = std::mem::transmute(objc_msgSend as *const ());
        let audio_type = mk_str(nss, str_sel, b"soun\0".as_ptr() as *const c_char);

        let cls = objc_getClass(b"AVCaptureDevice\0".as_ptr() as *const c_char);
        let sel = sel_registerName(b"authorizationStatusForMediaType:\0".as_ptr() as *const c_char);
        type AuthFn = unsafe extern "C" fn(*mut c_void, *const c_void, *mut c_void) -> isize;
        let auth_fn: AuthFn = std::mem::transmute(objc_msgSend as *const ());
        auth_fn(cls, sel, audio_type)
    }
}

#[cfg(target_os = "macos")]
fn ensure_microphone_access() -> Result<(), String> {
    use std::ffi::{c_char, c_void};
    match microphone_auth_status() {
        3 => return Ok(()),
        2 => {
            return Err(
                "Acceso al micrófono denegado. Ve a Ajustes del Sistema → Privacidad y seguridad \
                 → Micrófono y activa el permiso para Exocort."
                    .to_string(),
            )
        }
        1 => return Err("Acceso al micrófono restringido por el sistema.".to_string()),
        _ => {}
    }

    unsafe {
        let sema = dispatch_semaphore_create(0);
        let mut block = MicBlock {
            isa: &_NSConcreteStackBlock as *const c_void,
            flags: 0,
            reserved: 0,
            invoke: mic_block_invoke,
            descriptor: &MIC_BLOCK_DESCRIPTOR as *const MicBlockDescriptor,
            sema,
        };

        let nss = objc_getClass(b"NSString\0".as_ptr() as *const c_char);
        let str_sel = sel_registerName(b"stringWithUTF8String:\0".as_ptr() as *const c_char);
        type MkStr = unsafe extern "C" fn(*mut c_void, *const c_void, *const c_char) -> *mut c_void;
        let mk_str: MkStr = std::mem::transmute(objc_msgSend as *const ());
        let audio_type = mk_str(nss, str_sel, b"soun\0".as_ptr() as *const c_char);

        let cls = objc_getClass(b"AVCaptureDevice\0".as_ptr() as *const c_char);
        let req_sel = sel_registerName(
            b"requestAccessForMediaType:completionHandler:\0".as_ptr() as *const c_char,
        );
        type ReqFn = unsafe extern "C" fn(*mut c_void, *const c_void, *mut c_void, *mut MicBlock);
        let req_fn: ReqFn = std::mem::transmute(objc_msgSend as *const ());
        req_fn(cls, req_sel, audio_type, &mut block as *mut MicBlock);

        dispatch_semaphore_wait(sema, u64::MAX);
    }

    if microphone_auth_status() == 3 {
        Ok(())
    } else {
        Err(
            "Acceso al micrófono denegado. Ve a Ajustes del Sistema → Privacidad y seguridad \
             → Micrófono y activa el permiso para Exocort."
                .to_string(),
        )
    }
}

#[cfg(not(target_os = "macos"))]
fn ensure_microphone_access() -> Result<(), String> {
    Ok(())
}

fn backend_executable_path() -> Result<PathBuf, String> {
    #[cfg(target_os = "windows")]
    let candidates = [
        backend_root().join(".venv").join("Scripts").join("exocort.exe"),
        backend_root().join(".venv").join("bin").join("exocort.exe"),
    ];

    #[cfg(not(target_os = "windows"))]
    let candidates = [
        backend_root().join(".venv").join("bin").join("exocort"),
        backend_root().join(".venv").join("Scripts").join("exocort.exe"),
    ];

    for path in candidates {
        if path.exists() {
            return Ok(path);
        }
    }

    Err(format!(
        "No se encontró el ejecutable local de Exocort en {}.",
        backend_root().join(".venv").display()
    ))
}

fn backend_config_path(filename: &str) -> PathBuf {
    backend_root().join(filename)
}

#[cfg(target_os = "macos")]
fn has_screen_recording_access() -> bool {
    unsafe { CGPreflightScreenCaptureAccess() != 0 }
}

#[cfg(not(target_os = "macos"))]
fn has_screen_recording_access() -> bool {
    true
}

#[cfg(target_os = "macos")]
fn ensure_screen_recording_access() -> bool {
    if has_screen_recording_access() {
        return true;
    }

    let requested = unsafe { CGRequestScreenCaptureAccess() != 0 };
    requested || has_screen_recording_access()
}

#[cfg(not(target_os = "macos"))]
fn ensure_screen_recording_access() -> bool {
    true
}

fn config_uses_screen_capture(config: &Value) -> bool {
    config
        .get("capturer")
        .and_then(Value::as_object)
        .and_then(|capturer| capturer.get("screen"))
        .and_then(Value::as_object)
        .and_then(|screen| screen.get("enabled"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

fn config_without_screen_capture(config: &Value) -> Value {
    let mut config = config.clone();
    if let Some(capturer) = config.get_mut("capturer").and_then(Value::as_object_mut) {
        if let Some(screen) = capturer.get_mut("screen").and_then(Value::as_object_mut) {
            screen.insert("enabled".to_string(), Value::Bool(false));
        }
    }
    config
}

fn temp_screenless_config_path(config_path: &Path) -> Result<PathBuf, String> {
    let file_name = config_path.file_name().ok_or_else(|| {
        "No se pudo determinar el nombre de la configuracion temporal.".to_string()
    })?;
    let mut path = backend_root().join(file_name);
    path.set_extension("screenless.yaml");
    Ok(path)
}

fn clear_temp_backend_config(state: &BackendState) {
    if let Ok(mut guard) = state.temp_config.lock() {
        if let Some(path) = guard.take() {
            let _ = fs::remove_file(path);
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase", default)]
struct UiState {
    #[serde(default = "default_active_config")]
    active_config: String,
    #[serde(default)]
    env_overrides: HashMap<String, HashMap<String, String>>,
}

fn default_active_config() -> String {
    "config.yaml".to_string()
}

fn read_ui_state() -> Result<UiState, String> {
    let path = ui_state_path();
    let text = match fs::read_to_string(&path) {
        Ok(text) => text,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            return Ok(UiState::default());
        }
        Err(err) => return Err(format!("No se pudo leer {}: {}", path.display(), err)),
    };

    match serde_yaml::from_str::<UiState>(&text) {
        Ok(state) => Ok(state),
        Err(_) => Ok(UiState::default()),
    }
}

fn write_ui_state(state: &UiState) -> Result<UiState, String> {
    let path = ui_state_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("No se pudo crear {}: {}", parent.display(), err))?;
    }
    let text = serde_yaml::to_string(state)
        .map_err(|err| format!("No se pudo serializar el estado de UI: {}", err))?;
    fs::write(&path, text).map_err(|err| format!("No se pudo escribir {}: {}", path.display(), err))?;
    Ok(state.clone())
}

fn normalize_config_name(name: &str) -> Result<String, String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err("El nombre de la configuracion no puede estar vacio.".to_string());
    }
    if trimmed.contains('/') || trimmed.contains('\\') || trimmed.contains("..") {
        return Err("El nombre de la configuracion no puede contener rutas.".to_string());
    }

    let lower = trimmed.to_ascii_lowercase();
    if lower.ends_with(".yaml") || lower.ends_with(".yml") {
        Ok(trimmed.to_string())
    } else {
        Ok(format!("{trimmed}.yaml"))
    }
}

fn list_managed_config_names() -> Result<Vec<String>, String> {
    let dir = backend_root();
    let mut names = Vec::new();
    let entries = match fs::read_dir(&dir) {
        Ok(entries) => entries,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(names),
        Err(err) => {
            return Err(format!("No se pudo leer {}: {}", dir.display(), err));
        }
    };

    for entry in entries {
        let entry = entry.map_err(|err| format!("No se pudo leer {}: {}", dir.display(), err))?;
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let Some(extension) = path.extension().and_then(|value| value.to_str()) else {
            continue;
        };
        if extension != "yaml" && extension != "yml" {
            continue;
        }
        if let Some(name) = path.file_name().and_then(|value| value.to_str()) {
            names.push(name.to_string());
        }
    }

    names.sort_by(|left, right| {
        let left_priority = if left == "config.yaml" { 0 } else { 1 };
        let right_priority = if right == "config.yaml" { 0 } else { 1 };
        left_priority
            .cmp(&right_priority)
            .then_with(|| left.to_lowercase().cmp(&right.to_lowercase()))
    });
    Ok(names)
}

fn read_yaml_file(path: &Path) -> Result<Value, String> {
    let text = fs::read_to_string(path)
        .map_err(|err| format!("No se pudo leer {}: {}", path.display(), err))?;
    let yaml_value: serde_yaml::Value = serde_yaml::from_str(&text)
        .map_err(|err| format!("No se pudo parsear {}: {}", path.display(), err))?;
    serde_json::to_value(yaml_value)
        .map_err(|err| format!("No se pudo convertir {} a JSON: {}", path.display(), err))
}

fn write_yaml_file(path: &Path, config: &Value) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("No se pudo crear {}: {}", parent.display(), err))?;
    }
    let yaml = serde_yaml::to_string(config)
        .map_err(|err| format!("No se pudo serializar la configuracion: {}", err))?;
    fs::write(path, yaml).map_err(|err| format!("No se pudo escribir {}: {}", path.display(), err))
}

fn active_config_name() -> Result<String, String> {
    let configs = list_managed_config_names()?;
    if configs.is_empty() {
        return Err("No hay configuraciones disponibles.".to_string());
    }

    let state = read_ui_state()?;
    let current_active = state.active_config.clone();
    let active = if configs.contains(&current_active) {
        current_active
    } else if configs.iter().any(|name| name == "config.yaml") {
        "config.yaml".to_string()
    } else {
        configs
            .first()
            .cloned()
            .ok_or_else(|| "No hay configuraciones disponibles.".to_string())?
    };

    if state.active_config != active {
        write_ui_state(&UiState {
            active_config: active.clone(),
            env_overrides: state.env_overrides,
        })?;
    }

    Ok(active)
}

fn persist_active_config(active_config: &str) -> Result<(), String> {
    let mut state = read_ui_state()?;
    state.active_config = normalize_config_name(active_config)?;
    write_ui_state(&state).map(|_| ())
}

fn config_catalog() -> Result<ConfigCatalog, String> {
    let active_config = active_config_name()?;
    let configs = list_managed_config_names()?;
    Ok(ConfigCatalog {
        configs,
        active_config,
    })
}

fn load_config_value(name: &str) -> Result<Value, String> {
    let config_name = normalize_config_name(name)?;
    let path = backend_root().join(config_name);
    if !path.exists() {
        return Err(format!("No existe la configuracion {}.", path.display()));
    }
    read_yaml_file(&path)
}

fn save_config_value(name: &str, config: &Value) -> Result<PathBuf, String> {
    let config_name = normalize_config_name(name)?;
    let path = backend_root().join(config_name);
    write_yaml_file(&path, config)?;
    Ok(path)
}

fn load_yaml_defaults() -> Result<Value, String> {
    let active = active_config_name()?;
    let mut config = load_config_value(&active)?;
    let state = read_ui_state()?;
    let env_overrides = state
        .env_overrides
        .get(&active)
        .cloned()
        .unwrap_or_default();
    if let Some(object) = config.as_object_mut() {
        object.insert(
            "env_overrides".to_string(),
            serde_json::to_value(env_overrides).map_err(|err| {
                format!("No se pudo serializar las variables de entorno: {}", err)
            })?,
        );
    }
    Ok(config)
}

fn save_env_overrides(active_config: &str, env_overrides: &HashMap<String, String>) -> Result<(), String> {
    let normalized = normalize_config_name(active_config)?;
    let mut state = read_ui_state()?;
    state.env_overrides.insert(normalized, env_overrides.clone());
    write_ui_state(&state).map(|_| ())
}

fn create_config_from_template(name: &str) -> Result<PathBuf, String> {
    let config_name = normalize_config_name(name)?;
    let target = backend_root().join(&config_name);
    if target.exists() {
        return Err(format!("La configuracion {} ya existe.", config_name));
    }
    let source = backend_config_path("config.yaml");
    fs::copy(&source, &target).map_err(|err| {
        format!(
            "No se pudo copiar {} a {}: {}",
            source.display(),
            target.display(),
            err
        )
    })?;
    Ok(target)
}

fn duplicate_config_file(source_name: &str, target_name: &str) -> Result<PathBuf, String> {
    let source = backend_root().join(normalize_config_name(source_name)?);
    if !source.exists() {
        return Err(format!(
            "No existe la configuracion origen {}.",
            source.display()
        ));
    }
    let target_name = normalize_config_name(target_name)?;
    let target = backend_root().join(&target_name);
    if target.exists() {
        return Err(format!("La configuracion {} ya existe.", target_name));
    }
    fs::copy(&source, &target).map_err(|err| {
        format!(
            "No se pudo duplicar {} a {}: {}",
            source.display(),
            target.display(),
            err
        )
    })?;
    Ok(target)
}

fn rename_config_file(source_name: &str, target_name: &str) -> Result<PathBuf, String> {
    let source = backend_root().join(normalize_config_name(source_name)?);
    if !source.exists() {
        return Err(format!(
            "No existe la configuracion origen {}.",
            source.display()
        ));
    }
    let target_name = normalize_config_name(target_name)?;
    let target = backend_root().join(&target_name);
    if target.exists() {
        return Err(format!("La configuracion {} ya existe.", target_name));
    }
    fs::rename(&source, &target).map_err(|err| {
        format!(
            "No se pudo renombrar {} a {}: {}",
            source.display(),
            target.display(),
            err
        )
    })?;
    Ok(target)
}

fn delete_config_file(name: &str) -> Result<ConfigCatalog, String> {
    let config_name = normalize_config_name(name)?;
    let normalized_config_name = config_name.clone();
    let target = backend_root().join(&config_name);
    let configs_before = list_managed_config_names()?;
    if !target.exists() {
        return Err(format!("No existe la configuracion {}.", config_name));
    }
    if configs_before.len() <= 1 {
        return Err("Debe quedar al menos una configuracion.".to_string());
    }
    fs::remove_file(&target)
        .map_err(|err| format!("No se pudo borrar {}: {}", target.display(), err))?;
    let configs_after = list_managed_config_names()?;
    let active_config = if configs_after
        .iter()
        .any(|candidate| candidate == &config_name)
    {
        config_name
    } else if configs_after
        .iter()
        .any(|candidate| candidate == "config.yaml")
    {
        "config.yaml".to_string()
    } else {
        configs_after
            .first()
            .cloned()
            .ok_or_else(|| "No quedaron configuraciones disponibles.".to_string())?
    };
    let mut state = read_ui_state()?;
    state.active_config = active_config.clone();
    state.env_overrides.remove(&normalized_config_name);
    write_ui_state(&state)?;
    Ok(ConfigCatalog {
        configs: configs_after,
        active_config,
    })
}

fn set_active_config_file(name: &str) -> Result<ConfigCatalog, String> {
    let config_name = normalize_config_name(name)?;
    let configs = list_managed_config_names()?;
    if !configs.iter().any(|candidate| candidate == &config_name) {
        return Err(format!("No existe la configuracion {}.", config_name));
    }
    persist_active_config(&config_name)?;
    Ok(ConfigCatalog {
        configs,
        active_config: config_name,
    })
}

fn reset_backend_logs(state: &BackendState) -> Result<(), String> {
    let mut logs = state
        .logs
        .lock()
        .map_err(|_| "No se pudo acceder a los logs del backend.".to_string())?;
    logs.entries.clear();
    logs.next_seq = 0;
    Ok(())
}

#[tauri::command(rename_all = "camelCase")]
fn clear_backend_logs(state: State<BackendState>) -> Result<(), String> {
    reset_backend_logs(&state)
}

fn push_backend_log(logs: &Arc<Mutex<BackendLogs>>, stream: &str, message: String) {
    if let Ok(mut guard) = logs.lock() {
        let seq = guard.next_seq;
        guard.next_seq += 1;
        guard.entries.push(BackendLogEntry {
            seq,
            stream: stream.to_string(),
            message,
        });
    }
}

fn read_backend_stream<R: std::io::Read + Send + 'static>(
    reader: R,
    logs: Arc<Mutex<BackendLogs>>,
    stream: &'static str,
) {
    let buffered = BufReader::new(reader);
    for line in buffered.lines() {
        match line {
            Ok(message) => push_backend_log(&logs, stream, message),
            Err(err) => {
                push_backend_log(&logs, stream, format!("No se pudo leer el log: {}", err));
                break;
            }
        }
    }
}

fn current_status(state: &BackendState) -> Result<BackendStatus, String> {
    let mut guard = state
        .child
        .lock()
        .map_err(|_| "No se pudo acceder al estado del backend.".to_string())?;

    if let Some(child) = guard.as_mut() {
        match child.try_wait() {
            Ok(Some(exit_status)) => {
                *guard = None;
                clear_temp_backend_config(state);
                Ok(BackendStatus {
                    running: false,
                    pid: None,
                    message: match exit_status.code() {
                        Some(code) => format!("Backend detenido. Codigo de salida {}", code),
                        None => "Backend detenido.".to_string(),
                    },
                })
            }
            Ok(None) => Ok(BackendStatus {
                running: true,
                pid: Some(child.id()),
                message: format!("Backend arrancado. PID {}", child.id()),
            }),
            Err(err) => Ok(BackendStatus {
                running: false,
                pid: None,
                message: format!("Error comprobando el backend: {}", err),
            }),
        }
    } else {
        Ok(BackendStatus {
            running: false,
            pid: None,
            message: "Backend parado.".to_string(),
        })
    }
}

fn stop_backend_locked(state: &BackendState) -> Result<BackendStatus, String> {
    let mut guard = state
        .child
        .lock()
        .map_err(|_| "No se pudo acceder al estado del backend.".to_string())?;

    let mut child = match guard.take() {
        Some(child) => child,
        None => {
            return Ok(BackendStatus {
                running: false,
                pid: None,
                message: "Backend parado.".to_string(),
            });
        }
    };
    let pid = child.id();

    match child.try_wait() {
        Ok(Some(_)) => {}
        Ok(None) => {
            #[cfg(unix)]
            {
                let _ = Command::new("kill")
                    .arg("-TERM")
                    .arg(format!("-{}", pid))
                    .status();
                thread::sleep(Duration::from_millis(500));
                if child
                    .try_wait()
                    .map_err(|err| {
                        format!("No se pudo comprobar el backend antes de pararlo: {}", err)
                    })?
                    .is_none()
                {
                    let _ = Command::new("kill")
                        .arg("-KILL")
                        .arg(format!("-{}", pid))
                        .status();
                }
                let _ = child.wait();
            }

            #[cfg(windows)]
            {
                let _ = Command::new("taskkill")
                    .args(["/PID", &pid.to_string(), "/T", "/F"])
                    .status();
                let _ = child.wait();
            }
        }
        Err(err) => {
            return Err(format!(
                "No se pudo comprobar el backend antes de pararlo: {}",
                err
            ));
        }
    }

    clear_temp_backend_config(state);

    Ok(BackendStatus {
        running: false,
        pid: None,
        message: "Backend parado.".to_string(),
    })
}

#[tauri::command]
fn load_defaults(_app: AppHandle) -> Result<Value, String> {
    load_yaml_defaults()
}

#[tauri::command(rename_all = "camelCase")]
fn load_config_catalog(_app: AppHandle) -> Result<ConfigCatalog, String> {
    config_catalog()
}

#[tauri::command(rename_all = "camelCase")]
fn save_backend_config(
    _app: AppHandle,
    active_config: String,
    config: Value,
    env_overrides: HashMap<String, String>,
) -> Result<(), String> {
    save_config_value(&active_config, &config).map(|_| ())?;
    save_env_overrides(&active_config, &env_overrides)
}

#[tauri::command(rename_all = "camelCase")]
fn set_active_config(_app: AppHandle, config_name: String) -> Result<ConfigCatalog, String> {
    set_active_config_file(&config_name)
}

#[tauri::command(rename_all = "camelCase")]
fn create_config(_app: AppHandle, config_name: String) -> Result<ConfigCatalog, String> {
    let path = create_config_from_template(&config_name)?;
    let active = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "No se pudo determinar la configuracion creada.".to_string())?;
    save_env_overrides(active, &HashMap::new())?;
    set_active_config_file(active)
}

#[tauri::command(rename_all = "camelCase")]
fn duplicate_config(
    _app: AppHandle,
    source_config: String,
    target_config: String,
) -> Result<ConfigCatalog, String> {
    let path = duplicate_config_file(&source_config, &target_config)?;
    let active = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "No se pudo determinar la configuracion duplicada.".to_string())?;
    let mut state = read_ui_state()?;
    let source_name = normalize_config_name(&source_config)?;
    let target_name = normalize_config_name(active)?;
    let copied = state
        .env_overrides
        .get(&source_name)
        .cloned()
        .unwrap_or_default();
    state.env_overrides.insert(target_name, copied);
    write_ui_state(&UiState {
        active_config: state.active_config,
        env_overrides: state.env_overrides,
    })?;
    set_active_config_file(active)
}

#[tauri::command(rename_all = "camelCase")]
fn rename_config(
    _app: AppHandle,
    source_config: String,
    target_config: String,
) -> Result<ConfigCatalog, String> {
    let path = rename_config_file(&source_config, &target_config)?;
    let active = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "No se pudo determinar la configuracion renombrada.".to_string())?;
    let mut state = read_ui_state()?;
    let source_name = normalize_config_name(&source_config)?;
    let target_name = normalize_config_name(active)?;
    if let Some(env) = state.env_overrides.remove(&source_name) {
        state.env_overrides.insert(target_name, env);
    }
    write_ui_state(&UiState {
        active_config: state.active_config,
        env_overrides: state.env_overrides,
    })?;
    set_active_config_file(active)
}

#[tauri::command(rename_all = "camelCase")]
fn delete_config(_app: AppHandle, config_name: String) -> Result<ConfigCatalog, String> {
    let result = delete_config_file(&config_name)?;
    let normalized = normalize_config_name(&config_name)?;
    let mut state = read_ui_state()?;
    state.env_overrides.remove(&normalized);
    state.active_config = result.active_config.clone();
    write_ui_state(&state)?;
    Ok(result)
}

#[tauri::command]
fn get_backend_status(state: State<BackendState>) -> Result<BackendStatus, String> {
    current_status(&state)
}

#[tauri::command]
fn stop_backend(state: State<BackendState>) -> Result<BackendStatus, String> {
    stop_backend_locked(&state)
}

#[tauri::command(rename_all = "camelCase")]
fn get_backend_logs(
    state: State<BackendState>,
    since_seq: Option<u64>,
) -> Result<BackendLogBatch, String> {
    let logs = state
        .logs
        .lock()
        .map_err(|_| "No se pudo acceder a los logs del backend.".to_string())?;
    let since_seq = since_seq.unwrap_or(0);
    let entries = logs
        .entries
        .iter()
        .filter(|entry| entry.seq >= since_seq)
        .cloned()
        .collect();

    Ok(BackendLogBatch {
        entries,
        next_seq: logs.next_seq,
    })
}

fn start_backend_inner(
    _app: &AppHandle,
    state: &BackendState,
    active_config: String,
    config: Value,
    env_overrides: HashMap<String, String>,
) -> Result<BackendStatus, String> {
    if current_status(state)?.running {
        return current_status(state);
    }

    let config_path = save_config_value(&active_config, &config)?;
    reset_backend_logs(state)?;

    let mut run_config_path = config_path.clone();
    let screen_capture_requested = config_uses_screen_capture(&config);
    let screen_capture_suppressed = screen_capture_requested && !ensure_screen_recording_access();
    if screen_capture_suppressed {
        run_config_path = temp_screenless_config_path(&config_path)?;
        let temp_config = config_without_screen_capture(&config);
        write_yaml_file(&run_config_path, &temp_config)?;
    }

    let executable = backend_executable_path()?;
    let mut command = Command::new(&executable);
    command.current_dir(
        config_path
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(backend_root),
    );
    command.arg("--config").arg(&run_config_path);
    command.stdin(Stdio::null());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    command.env("PYTHONUNBUFFERED", "1");
    #[cfg(unix)]
    command.process_group(0);
    for (key, value) in env_overrides {
        command.env(key, value);
    }

    let mut child = command.spawn().map_err(|err| {
        if screen_capture_suppressed {
            let _ = fs::remove_file(&run_config_path);
        }
        format!("No se pudo arrancar {}: {}", executable.display(), err)
    })?;
    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    let stdout_logs = Arc::clone(&state.logs);
    let stderr_logs = Arc::clone(&state.logs);

    if let Some(stdout) = stdout {
        thread::spawn(move || read_backend_stream(stdout, stdout_logs, "stdout"));
    }
    if let Some(stderr) = stderr {
        thread::spawn(move || read_backend_stream(stderr, stderr_logs, "stderr"));
    }

    let startup_deadline = Instant::now() + Duration::from_secs(2);
    loop {
        match child.try_wait() {
            Ok(Some(exit_status)) => {
                let message = match exit_status.code() {
                    Some(code) => format!(
                        "El backend se cerró al arrancar con código {}. Revisa los logs para ver si faltan permisos de micrófono.",
                        code
                    ),
                    None => "El backend se cerró al arrancar. Revisa los logs para ver si faltan permisos de micrófono.".to_string(),
                };
                if screen_capture_suppressed {
                    let _ = fs::remove_file(&run_config_path);
                }
                return Err(message);
            }
            Ok(None) => {
                if Instant::now() >= startup_deadline {
                    break;
                }
                thread::sleep(Duration::from_millis(100));
            }
            Err(err) => {
                if screen_capture_suppressed {
                    let _ = fs::remove_file(&run_config_path);
                }
                return Err(format!(
                    "No se pudo comprobar el arranque del backend: {}",
                    err
                ));
            }
        }
    }

    let pid = child.id();
    let mut guard = state
        .child
        .lock()
        .map_err(|_| "No se pudo guardar el proceso del backend.".to_string())?;
    *guard = Some(child);
    if screen_capture_suppressed {
        if let Ok(mut temp_guard) = state.temp_config.lock() {
            *temp_guard = Some(run_config_path);
        }
    }

    let message = if screen_capture_suppressed {
        format!(
            "Backend arrancado. PID {}. Captura de pantalla desactivada hasta conceder permiso en macOS. Activa Exocort en Ajustes del sistema > Privacidad y seguridad > Grabación de pantalla y vuelve a abrir la app o reintenta arrancar el backend.",
            pid
        )
    } else {
        format!("Backend arrancado. PID {}", pid)
    };

    Ok(BackendStatus {
        running: true,
        pid: Some(pid),
        message,
    })
}

#[tauri::command(rename_all = "camelCase")]
fn start_backend(
    app: AppHandle,
    state: State<BackendState>,
    active_config: String,
    config: Value,
    env_overrides: HashMap<String, String>,
) -> Result<BackendStatus, String> {
    start_backend_inner(&app, &state, active_config, config, env_overrides)
}

// ─── Captures / activity viewer ─────────────────────────────────────────────

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct CaptureFile {
    kind: String,
    name: String,
    path: String,
    size_bytes: u64,
    modified_ms: u64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct CaptureList {
    files: Vec<CaptureFile>,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ActivityFile {
    name: String,
    path: String,
    size_bytes: u64,
    modified_ms: u64,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ActivityNoteRef {
    id: String,
    title: String,
    path: String,
    modified_ms: u64,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ActivityItemRef {
    id: String,
    kind: String,
    captured_ms: u64,
    source_available: bool,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ActivityItem {
    id: String,
    kind: String,
    captured_ms: u64,
    updated_ms: u64,
    source_file: Option<ActivityFile>,
    source_available: bool,
    processed: Option<ActivityFile>,
    processed_status: String,
    text: String,
    content_rule: Option<String>,
    content_match_type: Option<String>,
    content_pattern: Option<String>,
    related_notes: Vec<ActivityNoteRef>,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ActivityNote {
    id: String,
    title: String,
    path: String,
    modified_ms: u64,
    related_items: Vec<ActivityItemRef>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ActivityList {
    items: Vec<ActivityItem>,
    notes: Vec<ActivityNote>,
}

#[derive(Default)]
struct ActivityDraft {
    id: String,
    kind: String,
    captured_ms: u64,
    updated_ms: u64,
    source_file: Option<ActivityFile>,
    source_available: bool,
    processed: Option<ActivityFile>,
    processed_status: String,
    text: String,
    content_rule: Option<String>,
    content_match_type: Option<String>,
    content_pattern: Option<String>,
}

fn captures_data_root(_app: &AppHandle) -> Result<PathBuf, String> {
    Ok(repo_tmp_root())
}

fn allowed_data_roots(app: &AppHandle) -> Result<Vec<PathBuf>, String> {
    let mut roots = vec![captures_data_root(app)?, repo_vault_root()];
    for root in &mut roots {
        if let Ok(canonical) = root.canonicalize() {
            *root = canonical;
        }
    }
    roots.sort();
    roots.dedup();
    Ok(roots)
}

fn path_within_any_root(path: &Path, roots: &[PathBuf]) -> bool {
    roots.iter().any(|root| path.starts_with(root))
}

fn modified_ms_from_meta(meta: &fs::Metadata) -> u64 {
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn created_ms_from_meta(meta: &fs::Metadata) -> u64 {
    meta.created()
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn activity_file_from_path(path: &Path) -> Option<ActivityFile> {
    let Ok(meta) = fs::metadata(path) else {
        return None;
    };
    if !meta.is_file() {
        return None;
    }
    let name = path.file_name()?.to_str()?.to_string();
    Some(ActivityFile {
        name,
        path: path.to_string_lossy().into_owned(),
        size_bytes: meta.len(),
        modified_ms: modified_ms_from_meta(&meta),
    })
}

fn push_file(dir: &Path, name: String, kind: &str, files: &mut Vec<CaptureFile>) {
    let path = dir.join(&name);
    let Ok(meta) = fs::metadata(&path) else {
        return;
    };
    if !meta.is_file() {
        return;
    }
    let modified_ms = modified_ms_from_meta(&meta);
    files.push(CaptureFile {
        kind: kind.to_string(),
        name,
        path: path.to_string_lossy().into_owned(),
        size_bytes: meta.len(),
        modified_ms,
    });
}

fn scan_flat(dir: &Path, extensions: &[&str], kind: &str, files: &mut Vec<CaptureFile>) {
    if !dir.is_dir() {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let p = entry.path();
        if !p.is_file() {
            continue;
        }
        let name = match p.file_name().and_then(|n| n.to_str()) {
            Some(n) => n.to_string(),
            None => continue,
        };
        let ext = p
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_lowercase();
        if extensions.contains(&ext.as_str()) {
            push_file(dir, name, kind, files);
        }
    }
}

fn scan_processed(
    dir: &Path,
    normal_kind: &str,
    sensitive_kind: &str,
    files: &mut Vec<CaptureFile>,
) {
    if !dir.is_dir() {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let p = entry.path();
        if !p.is_file() {
            continue;
        }
        let name = match p.file_name().and_then(|n| n.to_str()) {
            Some(n) => n.to_string(),
            None => continue,
        };
        if !name.ends_with(".json") {
            continue;
        }
        let kind = if name.ends_with(".sensitive.json") {
            sensitive_kind
        } else {
            normal_kind
        };
        push_file(dir, name, kind, files);
    }
}

fn scan_vault(dir: &Path, files: &mut Vec<CaptureFile>) {
    if !dir.is_dir() {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let p = entry.path();
        if p.is_dir() {
            scan_vault(&p, files);
            continue;
        }
        if !p.is_file() {
            continue;
        }
        let name = match p.file_name().and_then(|n| n.to_str()) {
            Some(n) => n.to_string(),
            None => continue,
        };
        if name.ends_with(".md") {
            if let Some(parent) = p.parent() {
                push_file(parent, name, "note", files);
            }
        }
    }
}

fn collect_vault_note_paths(dir: &Path, note_paths: &mut Vec<PathBuf>) {
    if !dir.is_dir() {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_vault_note_paths(&path, note_paths);
            continue;
        }
        if path.is_file() && path.extension().and_then(|ext| ext.to_str()) == Some("md") {
            note_paths.push(path);
        }
    }
}

fn path_key(path: &Path) -> String {
    path.canonicalize()
        .unwrap_or_else(|_| path.to_path_buf())
        .to_string_lossy()
        .into_owned()
}

fn activity_id(kind: &str, key: &str) -> String {
    format!("{}:{}", kind, key)
}

fn source_path_from_payload(root: &Path, payload: &Value) -> Option<PathBuf> {
    if let Some(source_file) = payload.get("source_file").and_then(Value::as_str) {
        return Some(PathBuf::from(source_file));
    }
    payload
        .get("source_relpath")
        .and_then(Value::as_str)
        .map(|rel| root.join("raw").join(rel))
}

fn artifact_id_from_path(processed_root: &Path, path: &Path) -> Option<String> {
    path.strip_prefix(processed_root)
        .ok()
        .map(|value| value.to_string_lossy().replace('\\', "/"))
}

fn note_title_from_name(name: &str) -> String {
    name.trim_end_matches(".md").replace(['_', '-'], " ")
}

fn load_note_links(notes_state_dir: &Path) -> HashMap<String, HashSet<String>> {
    let mut links: HashMap<String, HashSet<String>> = HashMap::new();
    let batch_dir = notes_state_dir.join("batches");
    if !batch_dir.is_dir() {
        return links;
    }
    let Ok(entries) = fs::read_dir(batch_dir) else {
        return links;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_file() || path.extension().and_then(|ext| ext.to_str()) != Some("json") {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(payload) = serde_json::from_str::<Value>(&text) else {
            continue;
        };
        if payload.get("status").and_then(Value::as_str) != Some("completed") {
            continue;
        }
        let artifact_ids: Vec<String> = payload
            .get("artifact_ids")
            .and_then(Value::as_array)
            .map(|values| {
                values
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
        let note_paths: Vec<String> = payload
            .get("note_paths")
            .and_then(Value::as_array)
            .map(|values| {
                values
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
        if artifact_ids.is_empty() || note_paths.is_empty() {
            continue;
        }
        for note_path in note_paths {
            let bucket = links.entry(note_path).or_default();
            bucket.extend(artifact_ids.iter().cloned());
        }
    }
    links
}

fn ensure_activity_draft<'a>(
    drafts: &'a mut HashMap<String, ActivityDraft>,
    kind: &str,
    key: String,
) -> &'a mut ActivityDraft {
    drafts.entry(key.clone()).or_insert_with(|| ActivityDraft {
        id: activity_id(kind, &key),
        kind: kind.to_string(),
        processed_status: "pending".to_string(),
        ..ActivityDraft::default()
    })
}

fn assert_within_data_root(app: &AppHandle, file_path: &str) -> Result<PathBuf, String> {
    let roots = allowed_data_roots(app)?;
    let path = PathBuf::from(file_path);
    let canonical = path
        .canonicalize()
        .map_err(|_| "El archivo no existe o no es accesible.".to_string())?;
    if !path_within_any_root(&canonical, &roots) {
        return Err("Acceso denegado: ruta fuera del directorio de capturas.".to_string());
    }
    Ok(canonical)
}

fn resolve_delete_path_within_data_root(
    app: &AppHandle,
    file_path: &str,
) -> Result<PathBuf, String> {
    let roots = allowed_data_roots(app)?;
    let candidate = PathBuf::from(file_path);

    if let Ok(canonical) = candidate.canonicalize() {
        if path_within_any_root(&canonical, &roots) {
            return Ok(canonical);
        }
        return Err("Acceso denegado: ruta fuera del directorio de capturas.".to_string());
    }

    let Some(parent) = candidate.parent() else {
        return Err("El archivo no existe o no es accesible.".to_string());
    };
    let canonical_parent = parent
        .canonicalize()
        .map_err(|_| "El archivo no existe o no es accesible.".to_string())?;
    if !path_within_any_root(&canonical_parent, &roots) {
        return Err("Acceso denegado: ruta fuera del directorio de capturas.".to_string());
    }
    let Some(file_name) = candidate.file_name() else {
        return Err("El archivo no existe o no es accesible.".to_string());
    };
    Ok(canonical_parent.join(file_name))
}

#[tauri::command]
fn list_captures(app: AppHandle) -> Result<CaptureList, String> {
    let root = captures_data_root(&app)?;
    let vault_root = repo_vault_root();
    let mut files: Vec<CaptureFile> = Vec::new();

    scan_flat(
        &root.join("raw/audio"),
        &["wav", "mp3", "m4a"],
        "audio",
        &mut files,
    );
    scan_flat(
        &root.join("raw/screen"),
        &["png", "jpg", "jpeg", "webp"],
        "screen",
        &mut files,
    );
    scan_processed(
        &root.join("processed/audio"),
        "asr",
        "asr_sensitive",
        &mut files,
    );
    scan_processed(
        &root.join("processed/screen"),
        "ocr",
        "ocr_sensitive",
        &mut files,
    );
    scan_vault(&vault_root, &mut files);

    files.sort_by(|a, b| b.modified_ms.cmp(&a.modified_ms));
    Ok(CaptureList { files })
}

#[tauri::command]
fn list_activity(app: AppHandle) -> Result<ActivityList, String> {
    let root = captures_data_root(&app)?;
    let vault_root = repo_vault_root();
    let raw_root = root.join("raw");
    let processed_root = root.join("processed");
    let audio_raw_dir = raw_root.join("audio");
    let screen_raw_dir = raw_root.join("screen");
    let audio_processed_dir = processed_root.join("audio");
    let screen_processed_dir = processed_root.join("screen");
    let notes_state_dir = processed_root.join("notes");
    let vault_dir = vault_root;

    let mut drafts: HashMap<String, ActivityDraft> = HashMap::new();

    for (dir, kind) in [(&audio_raw_dir, "audio"), (&screen_raw_dir, "screen")] {
        if !dir.is_dir() {
            continue;
        }
        let Ok(entries) = fs::read_dir(dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let Some(source_file) = activity_file_from_path(&path) else {
                continue;
            };
            let key = path_key(&path);
            let draft = ensure_activity_draft(&mut drafts, kind, key);
            draft.captured_ms = source_file.modified_ms;
            draft.updated_ms = draft.updated_ms.max(source_file.modified_ms);
            draft.source_available = true;
            draft.source_file = Some(source_file);
        }
    }

    for (dir, kind) in [
        (&audio_processed_dir, "audio"),
        (&screen_processed_dir, "screen"),
    ] {
        if !dir.is_dir() {
            continue;
        }
        let Ok(entries) = fs::read_dir(dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() || path.extension().and_then(|ext| ext.to_str()) != Some("json") {
                continue;
            }
            let Some(processed_file) = activity_file_from_path(&path) else {
                continue;
            };
            let Ok(processed_meta) = fs::metadata(&path) else {
                continue;
            };
            let Ok(text) = fs::read_to_string(&path) else {
                continue;
            };
            let Ok(payload) = serde_json::from_str::<Value>(&text) else {
                continue;
            };

            let source_path = source_path_from_payload(&root, &payload);
            let key = source_path
                .as_ref()
                .map(|value| path_key(value))
                .unwrap_or_else(|| path_key(&path));
            let draft = ensure_activity_draft(&mut drafts, kind, key);

            draft.updated_ms = draft.updated_ms.max(processed_file.modified_ms);
            if draft.captured_ms == 0 {
                let fallback_captured_ms = created_ms_from_meta(&processed_meta);
                draft.captured_ms = if fallback_captured_ms > 0 {
                    fallback_captured_ms
                } else {
                    processed_file.modified_ms
                };
            }
            if let Some(source_path) = source_path {
                draft.source_available = source_path.exists();
                if draft.source_file.is_none() && draft.source_available {
                    draft.source_file = activity_file_from_path(&source_path);
                    if let Some(source_file) = &draft.source_file {
                        draft.captured_ms = source_file.modified_ms;
                        draft.updated_ms = draft.updated_ms.max(source_file.modified_ms);
                    }
                }
            }

            draft.processed = Some(processed_file);
            draft.processed_status =
                if payload.get("status").and_then(Value::as_str) == Some("blocked_sensitive") {
                    "blocked_sensitive".to_string()
                } else {
                    "processed".to_string()
                };
            draft.text = payload
                .get("text")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim()
                .to_string();
            draft.content_rule = payload
                .get("content_rule")
                .and_then(Value::as_str)
                .map(str::to_string);
            draft.content_match_type = payload
                .get("content_match_type")
                .and_then(Value::as_str)
                .map(str::to_string);
            draft.content_pattern = payload
                .get("content_pattern")
                .and_then(Value::as_str)
                .map(str::to_string);
        }
    }

    let mut items: Vec<ActivityItem> = drafts
        .into_values()
        .map(|draft| ActivityItem {
            id: draft.id,
            kind: draft.kind,
            captured_ms: draft.captured_ms,
            updated_ms: draft.updated_ms.max(draft.captured_ms),
            source_file: draft.source_file,
            source_available: draft.source_available,
            processed: draft.processed,
            processed_status: draft.processed_status,
            text: draft.text,
            content_rule: draft.content_rule,
            content_match_type: draft.content_match_type,
            content_pattern: draft.content_pattern,
            related_notes: Vec::new(),
        })
        .collect();

    let mut artifact_to_item: HashMap<String, usize> = HashMap::new();
    for (index, item) in items.iter().enumerate() {
        if let Some(processed) = &item.processed {
            let processed_path = PathBuf::from(&processed.path);
            if let Some(artifact_id) = artifact_id_from_path(&processed_root, &processed_path) {
                artifact_to_item.insert(artifact_id, index);
            }
        }
    }

    let note_links = load_note_links(&notes_state_dir);
    let mut note_paths = Vec::new();
    collect_vault_note_paths(&vault_dir, &mut note_paths);

    let mut notes = Vec::new();
    for note_path in note_paths {
        let Some(note_file) = activity_file_from_path(&note_path) else {
            continue;
        };
        let relative = note_path
            .strip_prefix(&vault_dir)
            .ok()
            .map(|value| value.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|| note_file.name.clone());
        let title = note_title_from_name(&note_file.name);
        let mut related_items = Vec::new();
        let mut seen_item_ids = HashSet::new();

        for artifact_id in note_links.get(&relative).into_iter().flatten() {
            if let Some(index) = artifact_to_item.get(artifact_id) {
                let item = &items[*index];
                if seen_item_ids.insert(item.id.clone()) {
                    related_items.push(ActivityItemRef {
                        id: item.id.clone(),
                        kind: item.kind.clone(),
                        captured_ms: item.captured_ms,
                        source_available: item.source_available,
                    });
                }
            }
        }
        related_items.sort_by(|a, b| {
            b.captured_ms
                .cmp(&a.captured_ms)
                .then_with(|| a.id.cmp(&b.id))
        });

        notes.push(ActivityNote {
            id: format!("note:{}", relative),
            title,
            path: note_file.path.clone(),
            modified_ms: note_file.modified_ms,
            related_items,
        });
    }

    let note_refs_by_item: HashMap<String, Vec<ActivityNoteRef>> =
        notes.iter().fold(HashMap::new(), |mut acc, note| {
            for related in &note.related_items {
                acc.entry(related.id.clone())
                    .or_default()
                    .push(ActivityNoteRef {
                        id: note.id.clone(),
                        title: note.title.clone(),
                        path: note.path.clone(),
                        modified_ms: note.modified_ms,
                    });
            }
            acc
        });

    for item in &mut items {
        if let Some(related_notes) = note_refs_by_item.get(&item.id) {
            item.related_notes = related_notes.clone();
            item.related_notes.sort_by(|a, b| {
                b.modified_ms
                    .cmp(&a.modified_ms)
                    .then_with(|| a.title.cmp(&b.title))
            });
        }
    }

    items.sort_by(|a, b| {
        b.captured_ms
            .cmp(&a.captured_ms)
            .then_with(|| a.id.cmp(&b.id))
    });
    notes.sort_by(|a, b| {
        b.modified_ms
            .cmp(&a.modified_ms)
            .then_with(|| a.title.cmp(&b.title))
    });

    Ok(ActivityList { items, notes })
}

#[tauri::command(rename_all = "camelCase")]
fn delete_activity_paths(app: AppHandle, paths: Vec<String>) -> Result<(), String> {
    let mut seen = HashSet::new();
    for file_path in paths {
        if !seen.insert(file_path.clone()) {
            continue;
        }
        let path = resolve_delete_path_within_data_root(&app, &file_path)?;
        if path.is_file() {
            match fs::remove_file(&path) {
                Ok(()) => {}
                Err(err) if err.kind() == std::io::ErrorKind::NotFound => {}
                Err(err) => return Err(format!("No se pudo borrar {}: {}", path.display(), err)),
            }
        }
    }
    Ok(())
}

#[tauri::command(rename_all = "camelCase")]
fn read_text_file(app: AppHandle, file_path: String) -> Result<String, String> {
    let path = assert_within_data_root(&app, &file_path)?;
    fs::read_to_string(&path).map_err(|err| format!("No se pudo leer el archivo: {}", err))
}

#[tauri::command(rename_all = "camelCase")]
fn read_file_as_base64(app: AppHandle, file_path: String) -> Result<String, String> {
    let path = assert_within_data_root(&app, &file_path)?;
    let bytes = fs::read(&path).map_err(|err| format!("No se pudo leer el archivo: {}", err))?;
    Ok(BASE64_STANDARD.encode(&bytes))
}

// ─── Services management ─────────────────────────────────────────────────────

struct ServiceDef {
    name: &'static str,
    dir: &'static str,
    script: &'static str,
    port: u16,
    description: &'static str,
}

const SERVICES: &[ServiceDef] = &[
    ServiceDef {
        name: "mac_asr",
        dir: "mac_asr",
        script: "mac-asr-service",
        port: 9092,
        description: "macOS native Speech Recognition ASR",
    },
    ServiceDef {
        name: "mac_ocr",
        dir: "mac_ocr",
        script: "mac-ocr-service",
        port: 9093,
        description: "macOS native Vision OCR",
    },
    ServiceDef {
        name: "faster_whisper",
        dir: "faster_whisper",
        script: "faster-whisper-service",
        port: 9000,
        description: "Local Faster Whisper ASR model",
    },
    ServiceDef {
        name: "llama_cpp",
        dir: "llama_cpp",
        script: "llama-cpp-service",
        port: 9100,
        description: "Local LLM via llama.cpp",
    },
];

struct ServiceEntry {
    child: Option<Child>,
    logs: Arc<Mutex<BackendLogs>>,
}

#[derive(Default)]
struct ServicesManager {
    entries: Mutex<HashMap<String, ServiceEntry>>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ServiceInfo {
    name: String,
    port: u16,
    description: String,
    running: bool,
    pid: Option<u32>,
}

fn managed_service_dir(dir: &str) -> PathBuf {
    services_root().join(dir)
}

fn managed_service_config_path(dir: &str) -> PathBuf {
    managed_service_dir(dir).join("config.yaml")
}

fn service_executable_path(def: &ServiceDef) -> Result<PathBuf, String> {
    #[cfg(target_os = "windows")]
    {
        let candidates = [
            managed_service_dir(def.dir)
                .join(".venv")
                .join("Scripts")
                .join(format!("{}.exe", def.script)),
            managed_service_dir(def.dir)
                .join(".venv")
                .join("bin")
                .join(format!("{}.exe", def.script)),
        ];
        for path in candidates {
            if path.exists() {
                return Ok(path);
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        let candidates = [
            managed_service_dir(def.dir).join(".venv").join("bin").join(def.script),
            managed_service_dir(def.dir)
                .join(".venv")
                .join("Scripts")
                .join(format!("{}.exe", def.script)),
        ];
        for path in candidates {
            if path.exists() {
                return Ok(path);
            }
        }
    }

    Err(format!(
        "No se encontró el ejecutable local del servicio {} en {}.",
        def.name,
        managed_service_dir(def.dir).join(".venv").display()
    ))
}

struct ResolvedServiceLaunch {
    executable: PathBuf,
    working_dir: PathBuf,
}

fn resolve_service_launch(
    def: &ServiceDef,
) -> Result<ResolvedServiceLaunch, String> {
    let config_path = managed_service_config_path(def.dir);
    if !config_path.exists() {
        return Err(format!(
            "No se encontró config.yaml para el servicio {} en {}.",
            def.name,
            config_path.display()
        ));
    }

    let executable = service_executable_path(def)?;
    Ok(ResolvedServiceLaunch {
        executable,
        working_dir: managed_service_dir(def.dir),
    })
}

fn check_service_entry(entry: &mut ServiceEntry) -> (bool, Option<u32>) {
    if let Some(child) = entry.child.as_mut() {
        match child.try_wait() {
            Ok(Some(_)) => {
                entry.child = None;
                (false, None)
            }
            Ok(None) => (true, Some(child.id())),
            Err(_) => {
                entry.child = None;
                (false, None)
            }
        }
    } else {
        (false, None)
    }
}

fn ensure_service_entry<'a>(
    entries: &'a mut HashMap<String, ServiceEntry>,
    service_name: &str,
) -> &'a mut ServiceEntry {
    entries
        .entry(service_name.to_string())
        .or_insert_with(|| ServiceEntry {
            child: None,
            logs: Arc::new(Mutex::new(BackendLogs::default())),
        })
}

fn stop_all_services(manager: &ServicesManager) {
    if let Ok(mut entries) = manager.entries.lock() {
        for entry in entries.values_mut() {
            stop_service_entry(entry);
        }
    }
}

fn stop_service_entry(entry: &mut ServiceEntry) {
    if let Some(mut child) = entry.child.take() {
        let pid = child.id();
        match child.try_wait() {
            Ok(Some(_)) => {}
            _ => {
                #[cfg(unix)]
                {
                    let _ = Command::new("kill")
                        .arg("-TERM")
                        .arg(format!("-{}", pid))
                        .status();
                    thread::sleep(Duration::from_millis(300));
                    if child.try_wait().map(|s| s.is_none()).unwrap_or(false) {
                        let _ = Command::new("kill")
                            .arg("-KILL")
                            .arg(format!("-{}", pid))
                            .status();
                    }
                    let _ = child.wait();
                }
                #[cfg(windows)]
                {
                    let _ = Command::new("taskkill")
                        .args(["/PID", &pid.to_string(), "/T", "/F"])
                        .status();
                    let _ = child.wait();
                }
            }
        }
    }
}

#[tauri::command(rename_all = "camelCase")]
fn list_services(state: State<ServicesManager>) -> Result<Vec<ServiceInfo>, String> {
    let mut entries = state
        .entries
        .lock()
        .map_err(|_| "No se pudo acceder al estado de los servicios.".to_string())?;
    let mut results = Vec::new();
    for def in SERVICES {
        let entry = ensure_service_entry(&mut entries, def.name);
        let (running, pid) = check_service_entry(entry);
        results.push(ServiceInfo {
            name: def.name.to_string(),
            port: def.port,
            description: def.description.to_string(),
            running,
            pid,
        });
    }
    Ok(results)
}

fn start_service_inner(
    _app: &AppHandle,
    state: &ServicesManager,
    service_name: &str,
) -> Result<ServiceInfo, String> {
    let def = SERVICES
        .iter()
        .find(|d| d.name == service_name)
        .ok_or_else(|| format!("Servicio desconocido: {}", service_name))?;
    let launch = resolve_service_launch(def)?;

    let mut entries = state
        .entries
        .lock()
        .map_err(|_| "No se pudo acceder al estado de los servicios.".to_string())?;
    let entry = ensure_service_entry(&mut entries, service_name);

    let (running, pid) = check_service_entry(entry);
    if running {
        return Ok(ServiceInfo {
            name: service_name.to_string(),
            port: def.port,
            description: def.description.to_string(),
            running: true,
            pid,
        });
    }

    if let Ok(mut logs) = entry.logs.lock() {
        logs.entries.clear();
        logs.next_seq = 0;
    }

    if service_name == "mac_asr" {
        ensure_microphone_access()?;
    }

    let mut command = Command::new(&launch.executable);
    command.current_dir(&launch.working_dir);
    command.stdin(Stdio::null());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    command.env("PYTHONUNBUFFERED", "1");
    #[cfg(unix)]
    command.process_group(0);

    let mut child = command.spawn().map_err(|err| {
        format!(
            "No se pudo arrancar {}: {}",
            launch.executable.display(),
            err
        )
    })?;

    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    let stdout_logs = Arc::clone(&entry.logs);
    let stderr_logs = Arc::clone(&entry.logs);

    if let Some(stdout) = stdout {
        thread::spawn(move || read_backend_stream(stdout, stdout_logs, "stdout"));
    }
    if let Some(stderr) = stderr {
        thread::spawn(move || read_backend_stream(stderr, stderr_logs, "stderr"));
    }

    let pid = child.id();
    entry.child = Some(child);

    Ok(ServiceInfo {
        name: service_name.to_string(),
        port: def.port,
        description: def.description.to_string(),
        running: true,
        pid: Some(pid),
    })
}

#[tauri::command(rename_all = "camelCase")]
fn start_service(
    app: AppHandle,
    service_name: String,
    state: State<ServicesManager>,
) -> Result<ServiceInfo, String> {
    start_service_inner(&app, &state, &service_name)
}

#[tauri::command(rename_all = "camelCase")]
fn stop_service(
    service_name: String,
    state: State<ServicesManager>,
) -> Result<ServiceInfo, String> {
    let def = SERVICES
        .iter()
        .find(|d| d.name == service_name)
        .ok_or_else(|| format!("Servicio desconocido: {}", service_name))?;

    let mut entries = state
        .entries
        .lock()
        .map_err(|_| "No se pudo acceder al estado de los servicios.".to_string())?;
    let entry = ensure_service_entry(&mut entries, &service_name);
    stop_service_entry(entry);

    Ok(ServiceInfo {
        name: service_name,
        port: def.port,
        description: def.description.to_string(),
        running: false,
        pid: None,
    })
}

#[tauri::command(rename_all = "camelCase")]
fn get_service_logs(
    service_name: String,
    since_seq: Option<u64>,
    state: State<ServicesManager>,
) -> Result<BackendLogBatch, String> {
    let logs_arc = {
        let entries = state
            .entries
            .lock()
            .map_err(|_| "No se pudo acceder al estado de los servicios.".to_string())?;
        match entries.get(&service_name) {
            Some(entry) => Arc::clone(&entry.logs),
            None => {
                return Ok(BackendLogBatch {
                    entries: vec![],
                    next_seq: 0,
                })
            }
        }
    };
    let logs = logs_arc
        .lock()
        .map_err(|_| "No se pudo acceder a los logs del servicio.".to_string())?;
    let since = since_seq.unwrap_or(0);
    let filtered = logs
        .entries
        .iter()
        .filter(|e| e.seq >= since)
        .cloned()
        .collect();
    Ok(BackendLogBatch {
        entries: filtered,
        next_seq: logs.next_seq,
    })
}

#[tauri::command(rename_all = "camelCase")]
fn load_service_config(_app: AppHandle, service_name: String) -> Result<Value, String> {
    let def = SERVICES
        .iter()
        .find(|d| d.name == service_name)
        .ok_or_else(|| format!("Servicio desconocido: {}", service_name))?;
    let config_path = managed_service_config_path(def.dir);
    if !config_path.exists() {
        return Err(format!(
            "No se encontró config.yaml en: {}",
            config_path.display()
        ));
    }
    read_yaml_file(&config_path)
}

#[tauri::command(rename_all = "camelCase")]
fn save_service_config(_app: AppHandle, service_name: String, config: Value) -> Result<(), String> {
    let def = SERVICES
        .iter()
        .find(|d| d.name == service_name)
        .ok_or_else(|| format!("Servicio desconocido: {}", service_name))?;
    let config_path = managed_service_config_path(def.dir);
    write_yaml_file(&config_path, &config)
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn hide_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

fn mark_exit_requested(app: &AppHandle) {
    let runtime = app.state::<AppRuntimeState>();
    if let Ok(mut exit_requested) = runtime.exit_requested.lock() {
        *exit_requested = true;
    };
}

fn exit_requested(app: &AppHandle) -> bool {
    let runtime = app.state::<AppRuntimeState>();
    runtime
        .exit_requested
        .lock()
        .map(|exit_requested| *exit_requested)
        .unwrap_or(false)
}

fn create_tray(app: &AppHandle) -> Result<(), tauri::Error> {
    let open_item = MenuItem::with_id(app, TRAY_OPEN_ID, "Abrir Exocort", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, TRAY_QUIT_ID, "Salir", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open_item, &quit_item])?;

    let mut tray = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            TRAY_OPEN_ID => show_main_window(app),
            TRAY_QUIT_ID => {
                mark_exit_requested(app);
                app.exit(0);
            }
            _ => {}
        });

    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }

    tray.build(app)?;
    Ok(())
}

fn main() {
    let mut builder = tauri::Builder::default()
        .manage(AppRuntimeState {
            exit_requested: Mutex::new(false),
        })
        .manage(BackendState::default())
        .manage(ServicesManager::default());

    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            show_main_window(app);
        }));
    }

    builder
        .setup(|app| {
            create_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            load_defaults,
            load_config_catalog,
            save_backend_config,
            set_active_config,
            create_config,
            duplicate_config,
            rename_config,
            delete_config,
            get_backend_status,
            get_backend_logs,
            clear_backend_logs,
            stop_backend,
            start_backend,
            list_captures,
            list_activity,
            delete_activity_paths,
            read_text_file,
            read_file_as_base64,
            list_services,
            start_service,
            stop_service,
            get_service_logs,
            load_service_config,
            save_service_config,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| match event {
            tauri::RunEvent::WindowEvent {
                label,
                event: tauri::WindowEvent::CloseRequested { api, .. },
                ..
            } if label == "main" && !exit_requested(app_handle) => {
                api.prevent_close();
                hide_main_window(app_handle);
            }
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
                let state = app_handle.state::<BackendState>();
                let _ = stop_backend_locked(&state);
                let services = app_handle.state::<ServicesManager>();
                stop_all_services(&services);
            }
            _ => {}
        });
}
