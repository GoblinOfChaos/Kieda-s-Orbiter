use std::thread::sleep;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use std::{error::Error, str::FromStr};
use std::{fs::File, thread};
use std::{
    io::{BufRead, BufReader, Seek, SeekFrom, Write},
    sync::mpsc::channel,
};
use std::{path::PathBuf, sync::mpsc};

use clap::Parser;
use env_logger::{Builder, Env};
use global_hotkey::{hotkey::HotKey, GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use image::DynamicImage;
use log::{debug, error, info, warn};
use notify::{watcher, RecursiveMode, Watcher};
use wfinfo::ownership::{OwnedDb, Ownership};
use wfinfo::{
    database::Database,
    ocr::{normalize_string, reward_image_to_reward_names, OCR},
    utils::fetch_prices_and_items,
};

fn monitor_geometry_from_env() -> (i32, i32, u32, u32) {
    if let Ok(s) = std::env::var("WFINFO_MONITOR_GEOMETRY") {
        let p: Vec<i32> = s.split(',').filter_map(|x| x.trim().parse().ok()).collect();
        if p.len() == 4 && p[2] > 0 && p[3] > 0 {
            return (p[0], p[1], p[2] as u32, p[3] as u32);
        }
    }

    let pt = std::env::var("WFINFO_MONITOR_POINT")
        .ok()
        .and_then(|s| {
            let p: Vec<i32> = s.split(',').filter_map(|x| x.trim().parse().ok()).collect();
            if p.len() == 2 {
                Some((p[0], p[1]))
            } else {
                None
            }
        })
        .unwrap_or((3200, 720));

    // Default setup: 2560x1440 Warframe monitor whose centre is WFINFO_MONITOR_POINT.
    (pt.0 - 1280, pt.1 - 720, 2560, 1440)
}

fn take_screenshot() -> Option<DynamicImage> {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    #[cfg(target_os = "windows")]
    {
        // On Windows: use xcap::Monitor directly — Windows GDI/DXGI API,
        // no focus stealing, no external tools needed.
        use xcap::Monitor;
        let (mx, my) = std::env::var("WFINFO_MONITOR_POINT")
            .ok()
            .and_then(|s| {
                let p: Vec<i32> = s.split(',').filter_map(|x| x.trim().parse().ok()).collect();
                if p.len() == 2 {
                    Some((p[0], p[1]))
                } else {
                    None
                }
            })
            .unwrap_or((960, 540)); // default: centre of primary 1920x1080

        let monitor = Monitor::from_point(mx, my)
            .or_else(|_| {
                Monitor::all().and_then(|m| {
                    m.into_iter()
                        .next()
                        .ok_or(xcap::XCapError::new("no monitors"))
                })
            })
            .ok()?;

        let frame = monitor.capture_image().ok()?;
        let image = DynamicImage::ImageRgba8(frame);
        info!("Screenshot via xcap: {}x{}", image.width(), image.height());
        let debug_path = format!(
            "{}\\wfinfo-capture-{ts}.png",
            std::env::temp_dir().display()
        );
        let _ = image.save(&debug_path);
        info!("Saved debug capture to {debug_path}");
        return Some(image);
    }

    #[cfg(not(target_os = "windows"))]
    {
        // On Linux/macOS: use spectacle (KDE portal) or grim (wlroots).
        // These are Wayland-native and don't cause gamescope focus loss.
        let path = "/tmp/wfinfo-capture-portal.png";
        let _ = std::fs::remove_file(path);

        let screenshot_tools: &[(&str, &[&str])] = &[
            (
                "/run/host/usr/bin/spectacle",
                &["-b", "-n", "--no-decoration", "-o", path],
            ),
            ("spectacle", &["-b", "-n", "--no-decoration", "-o", path]),
            ("/run/host/usr/bin/grim", &[path]),
            ("grim", &[path]),
        ];

        let mut captured_by = None;
        for (tool, args) in screenshot_tools {
            let ok = std::process::Command::new(tool)
                .args(*args)
                .status()
                .map(|s| s.success())
                .unwrap_or(false);
            if ok {
                captured_by = Some(*tool);
                break;
            }
        }

        let Some(tool) = captured_by else {
            error!("screenshot failed: neither spectacle nor grim worked");
            return None;
        };

        let mut image = match image::open(path) {
            Ok(img) => img,
            Err(e) => {
                error!("screenshot tool {tool} ran but image could not be opened: {e}");
                return None;
            }
        };

        info!(
            "Screenshot captured by {tool}: {}x{}",
            image.width(),
            image.height()
        );

        let (wx, wy, ww, wh) = monitor_geometry_from_env();
        if wx >= 0
            && wy >= 0
            && image.width() >= (wx as u32 + ww)
            && image.height() >= (wy as u32 + wh)
            && (image.width() != ww || image.height() != wh)
        {
            image = image.crop_imm(wx as u32, wy as u32, ww, wh);
            info!("Cropped screenshot to monitor geometry ({wx},{wy}) {ww}x{wh}");
        }

        let debug_path = format!("/tmp/wfinfo-capture-{ts}.png");
        if let Err(e) = image.save(&debug_path) {
            warn!("Failed to save debug capture {debug_path}: {e}");
        } else {
            info!("Saved debug capture to {debug_path}");
        }

        Some(image)
    }
}

fn run_detection(db: &Database, owned: &OwnedDb) {
    let image = match take_screenshot() {
        Some(img) => img,
        None => return,
    };
    info!("Captured");
    let raw_names = reward_image_to_reward_names(image, None);
    let cleaned: Vec<String> = raw_names.iter().map(|s| normalize_string(s)).collect();
    debug!("OCR: {:#?}", cleaned);

    let resolved: Vec<(String, Ownership)> = cleaned
        .iter()
        .map(|s| match db.find_item(s, None) {
            Some(item) => {
                let own = owned.lookup(&item.drop_name);
                (item.drop_name.clone(), own)
            }
            None => {
                warn!("could not resolve OCR text {:?} to a known item", s);
                (format!("? {}", s), Ownership::Unknown)
            }
        })
        .collect();

    info!("--- relic reward ownership ---");
    for (name, own) in &resolved {
        info!("  {:<40}  {}", name, own.colored());
    }

    // Desktop notifications are intentionally disabled. The overlay is the UI
    // for reward results, and host notifications steal focus from Warframe.
    // ── Write latest-detection.json for the Python overlay ───────────────
    let rewards_json: Vec<String> = resolved
        .iter()
        .map(|(name, own)| {
            let (status, count) = match own {
                Ownership::Owned(n) => ("OWNED", *n),
                Ownership::Need => ("NEED", 0),
                Ownership::Unknown => ("UNKNOWN", 0),
            };
            format!(
                r#"{{"name":{},"status":"{}","count":{}}}"#,
                serde_json::to_string(name).unwrap_or_default(),
                status,
                count,
            )
        })
        .collect();

    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    // Use configured monitor point for warframe geometry hint to the overlay
    let (wx, wy, ww, wh) = monitor_geometry_from_env();
    let state_json = format!(
        r#"{{"timestamp":{ts},"warframe":{{"x":{x},"y":{y},"width":{w},"height":{h}}},"rewards":[{rewards}]}}"#,
        ts = ts,
        x = wx,
        y = wy,
        w = ww,
        h = wh,
        rewards = rewards_json.join(","),
    );

    // Must match paths.py's _get_data_dir() exactly, or the Python side
    // (overlay.py) polls a completely different file than this writes to.
    let data_dir = if cfg!(windows) {
        std::env::var("APPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                PathBuf::from(std::env::var("USERPROFILE").unwrap_or_default())
                    .join("AppData/Roaming")
            })
    } else {
        std::env::var("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".local/share")
            })
    }
    .join("kiedas-orbiter");
    let _ = std::fs::create_dir_all(&data_dir);
    let state_path = data_dir.join("latest-detection.json");
    match File::create(&state_path).and_then(|mut f| f.write_all(state_json.as_bytes())) {
        Ok(_) => info!("Wrote state file: {}", state_path.display()),
        Err(e) => warn!("Failed to write state file: {}", e),
    }
}

fn log_watcher(path: PathBuf, event_sender: mpsc::Sender<()>) {
    debug!("Path: {}", path.display());
    let mut position = File::open(&path)
        .unwrap_or_else(|_| panic!("Couldn't open file {}", path.display()))
        .seek(SeekFrom::End(0))
        .unwrap();

    thread::spawn(move || {
        debug!("Position: {}", position);

        let (tx, rx) = mpsc::channel();
        let mut watcher = watcher(tx, Duration::from_millis(100)).unwrap();
        watcher
            .watch(&path, RecursiveMode::NonRecursive)
            .unwrap_or_else(|_| panic!("Failed to open EE.log file: {}", path.display()));

        loop {
            match rx.recv() {
                Ok(notify::DebouncedEvent::Write(_)) => {
                    let mut f = File::open(&path).unwrap();
                    f.seek(SeekFrom::Start(position)).unwrap();

                    let mut reward_screen_detected = false;

                    let reader = BufReader::new(std::io::Read::by_ref(&mut f));
                    for line in reader.lines() {
                        let line = match line {
                            Ok(line) => line,
                            Err(err) => {
                                error!("Error reading line: {}", err);
                                continue;
                            }
                        };
                        // debug!("> {:?}", line);
                        if line.contains("Pause countdown done")
                            || line.contains("Got rewards")
                            || line.contains("Created /Lotus/Interface/ProjectionRewardChoice.swf")
                        {
                            reward_screen_detected = true;
                        }
                    }

                    if reward_screen_detected {
                        info!("Detected, waiting...");
                        sleep(Duration::from_millis(1500));
                        event_sender.send(()).unwrap();
                    }

                    position = f.metadata().unwrap().len();
                    debug!("Log position: {}", position);
                }
                Ok(_) => {}
                Err(err) => {
                    error!("Error: {:?}", err);
                }
            }
        }
    });
}

fn hotkey_watcher(hotkey: HotKey, event_sender: mpsc::Sender<()>) {
    debug!("watching hotkey: {hotkey:?}");
    thread::spawn(move || {
        let manager = GlobalHotKeyManager::new().unwrap();
        manager.register(hotkey).unwrap();

        while let Ok(event) = GlobalHotKeyEvent::receiver().recv() {
            debug!("{:?}", event);
            if event.state == HotKeyState::Pressed {
                event_sender.send(()).unwrap();
            }
        }
    });
}

#[allow(dead_code)]
fn benchmark() -> Result<(), Box<dyn Error>> {
    for _ in 0..10 {
        let image = image::open("input3.png").unwrap();
        println!("Converted");
        let text = reward_image_to_reward_names(image, None);
        println!("got names");
        let text = text.iter().map(|s| normalize_string(s));
        println!("{:#?}", text);
    }
    // clean up tesseract
    drop(OCR.lock().unwrap().take());
    Ok(())
}

#[derive(Parser)]
#[command(version, about, long_about = None)]
struct Arguments {
    /// Path to the `EE.log` file located in the game installation directory
    ///
    /// Most likely located at `~/.local/share/Steam/steamapps/compatdata/230410/pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log`
    game_log_file_path: Option<PathBuf>,
    /// Warframe Window Name
    ///
    /// some systems may require the window name to be specified (e.g. when using gamescope)
    #[arg(short, long, default_value = "Warframe")]
    window_name: String,
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments = Arguments::parse();
    // HOME doesn't exist on Windows (it's USERPROFILE there), and this used
    // to unwrap() it unconditionally — eagerly evaluated even when
    // --game-log-file-path was already given, since unwrap_or() isn't lazy.
    // That panicked on every Windows launch. Only compute this fallback
    // path (and only touch env vars at all) if it's actually needed.
    let log_path = match arguments.game_log_file_path {
        Some(p) => p,
        None => {
            let home = std::env::var("HOME")
                .or_else(|_| std::env::var("USERPROFILE"))
                .unwrap_or_else(|_| ".".to_string());
            let home = PathBuf::from_str(&home).unwrap();
            if cfg!(windows) {
                home.join("AppData/Local/Warframe/EE.log")
            } else {
                home.join(".local/share/Steam/steamapps/compatdata/230410/pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log")
            }
        }
    };
    let window_name = arguments.window_name;
    let env = Env::default()
        .filter_or("WFINFO_LOG", "info")
        .write_style_or("WFINFO_STYLE", "always");
    Builder::from_env(env)
        .format_timestamp(None)
        .format_level(false)
        .format_module_path(false)
        .format_target(false)
        .init();

    // Screenshots are taken via spectacle/grim (Wayland-native portal).
    // No X11/XCB connection is made, so gamescope never releases its input grab.
    let _ = window_name; // kept for CLI compatibility

    let (prices, items) = fetch_prices_and_items()?;
    let db = Database::load_from_file(Some(&prices), Some(&items));

    // Load ownership data (owned_items.json next to the binary or in cwd)
    let owned_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("owned_items.json")))
        .filter(|p| p.exists())
        .unwrap_or_else(|| PathBuf::from("owned_items.json"));
    let owned = OwnedDb::load_or_empty(&owned_path);

    info!("Loaded database");

    let (event_sender, event_receiver) = channel();

    log_watcher(log_path, event_sender.clone());
    hotkey_watcher("F12".parse()?, event_sender);

    while let Ok(()) = event_receiver.recv() {
        info!("Capturing");
        run_detection(&db, &owned);
    }

    drop(OCR.lock().unwrap().take());
    Ok(())
}

#[cfg(test)]
mod test {
    use std::collections::BTreeMap;
    use std::fs::read_to_string;

    use image::io::Reader;
    use indexmap::IndexMap;
    use rayon::prelude::*;
    use tesseract::Tesseract;
    use wfinfo::ocr::detect_theme;
    use wfinfo::ocr::extract_parts;
    use wfinfo::testing::Label;

    use super::*;

    #[test]
    fn single_image() {
        let image = Reader::open(format!("test-images/{}.png", 1))
            .unwrap()
            .decode()
            .unwrap();
        let text = reward_image_to_reward_names(image, None);
        let text = text.iter().map(|s| normalize_string(s));
        println!("{:#?}", text);
        let db = Database::load_from_file(None, None);
        let items: Vec<_> = text.map(|s| db.find_item(&s, None)).collect();
        println!("{:#?}", items);

        assert_eq!(
            items[0].expect("Didn't find an item?").drop_name,
            "Octavia Prime Systems Blueprint"
        );
        assert_eq!(
            items[1].expect("Didn't find an item?").drop_name,
            "Octavia Prime Blueprint"
        );
        assert_eq!(
            items[2].expect("Didn't find an item?").drop_name,
            "Tenora Prime Blueprint"
        );
        assert_eq!(
            items[3].expect("Didn't find an item?").drop_name,
            "Harrow Prime Systems Blueprint"
        );
    }

    // #[test]
    #[allow(dead_code)]
    fn wfi_images_exact() {
        let labels: IndexMap<String, Label> =
            serde_json::from_str(&read_to_string("WFI test images/labels.json").unwrap()).unwrap();
        for (filename, label) in labels {
            let image = Reader::open("WFI test images/".to_string() + &filename)
                .unwrap()
                .decode()
                .unwrap();
            let text = reward_image_to_reward_names(image, None);
            let text: Vec<_> = text.iter().map(|s| normalize_string(s)).collect();
            println!("{:#?}", text);

            let db = Database::load_from_file(None, None);
            let items: Vec<_> = text.iter().map(|s| db.find_item(s, None)).collect();
            println!("{:#?}", items);
            println!("{}", filename);

            let item_names = items
                .iter()
                .map(|item| item.map(|item| item.drop_name.clone()));

            for (result, expectation) in item_names.zip(label.items) {
                if expectation.is_empty() {
                    assert_eq!(result, None)
                } else {
                    assert_eq!(result, Some(expectation))
                }
            }
        }
    }

    #[test]
    fn wfi_images_99_percent() {
        let labels: BTreeMap<String, Label> =
            serde_json::from_str(&read_to_string("WFI test images/labels.json").unwrap()).unwrap();
        let total = labels.len();
        let success_count: usize = labels
            .into_par_iter()
            .map(|(filename, label)| {
                let image = Reader::open("WFI test images/".to_string() + &filename)
                    .unwrap()
                    .decode()
                    .unwrap();
                let text = reward_image_to_reward_names(image, None);
                let text: Vec<_> = text.iter().map(|s| normalize_string(s)).collect();
                println!("{:#?}", text);

                let db = Database::load_from_file(None, None);
                let items: Vec<_> = text.iter().map(|s| db.find_item(s, None)).collect();
                println!("{:#?}", items);
                println!("{}", filename);

                let item_names = items
                    .iter()
                    .map(|item| item.map(|item| item.drop_name.clone()));

                if item_names.zip(label.items).all(|(result, expectation)| {
                    expectation == result.unwrap_or_else(|| "".to_string())
                }) {
                    1
                } else {
                    0
                }
            })
            .sum();

        let success_rate = success_count as f32 / total as f32;
        assert!(success_rate > 0.95, "Success rate: {success_rate}");
    }

    // #[test]
    #[allow(dead_code)]
    fn images() {
        let tests = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];
        for i in tests {
            let image = Reader::open(format!("test-images/{}.png", i))
                .unwrap()
                .decode()
                .unwrap();

            let theme = detect_theme(&image);
            println!("Theme: {:?}", theme);

            let parts = extract_parts(&image, theme);

            let mut ocr =
                Tesseract::new(None, Some("eng")).expect("Could not initialize Tesseract");
            for part in parts {
                let buffer = part.as_flat_samples_u8().unwrap();
                ocr = ocr
                    .set_frame(
                        buffer.samples,
                        part.width() as i32,
                        part.height() as i32,
                        3,
                        3 * part.width() as i32,
                    )
                    .expect("Failed to set image");
                let text = ocr.get_text().expect("Failed to get text");
                println!("{}", text);
            }
            println!("=================");
        }
    }
}
