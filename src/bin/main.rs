use std::thread::sleep;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use std::{error::Error, str::FromStr};
use std::{fs::File, thread};
use std::{
    io::{BufRead, BufReader, Read, Seek, SeekFrom, Write},
    sync::mpsc::channel,
};
use std::{path::PathBuf, sync::mpsc};

use clap::Parser;
use env_logger::{Builder, Env};
use global_hotkey::{hotkey::HotKey, GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use image::DynamicImage;
use log::{debug, error, info, warn};
use notify::{watcher, RecursiveMode, Watcher};
use xcap::Monitor;

use wfinfo::ownership::{notify, OwnedDb, Ownership};
use wfinfo::{
    database::Database,
    ocr::{normalize_string, reward_image_to_reward_names, OCR},
    utils::fetch_prices_and_items,
};

fn run_detection(capturer: &Monitor, db: &Database, owned: &OwnedDb) {
    let frame = match capturer.capture_image() {
        Ok(f) => f,
        Err(e) => {
            error!("screenshot failed: {e}");
            return;
        }
    };
    info!("Captured");
    let image = DynamicImage::ImageRgba8(frame);
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

    // Desktop notification — skipped if show_notifications=0 in config.json
    let notifications_enabled = std::fs::read_to_string(
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join("../../config.json")))
            .unwrap_or_else(|| PathBuf::from("config.json")),
    )
    .ok()
    .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
    .and_then(|v| v.get("show_notifications").and_then(|n| n.as_i64()))
    .unwrap_or(1)
        != 0;

    if notifications_enabled {
        let any_need = resolved.iter().any(|(_, o)| matches!(o, Ownership::Need));
        let body = resolved
            .iter()
            .map(|(n, o)| format!("• {}  —  {}", n, o.label()))
            .collect::<Vec<_>>()
            .join("\n");
        notify(
            "Relic rewards",
            &body,
            if any_need { "normal" } else { "low" },
        );
    }
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
    let state_json = format!(
        r#"{{"timestamp":{ts},"warframe":{{"x":{x},"y":{y},"width":{w},"height":{h}}},"rewards":[{rewards}]}}"#,
        ts = ts,
        x = capturer.x(),
        y = capturer.y(),
        w = capturer.width(),
        h = capturer.height(),
        rewards = rewards_json.join(","),
    );

    let data_dir = std::env::var("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".local/share")
        })
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
    let default_log_path = PathBuf::from_str(&std::env::var("HOME").unwrap()).unwrap().join(PathBuf::from_str(".local/share/Steam/steamapps/compatdata/230410/pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log")?);
    let log_path = arguments.game_log_file_path.unwrap_or(default_log_path);
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

    // Use Monitor capture instead of Window capture.
    // Window::all() enumerates XWayland windows which causes gamescope to
    // release its input grab from the game, stealing focus on every detection.
    // Monitor::from_point() captures the whole screen without any window lookup.
    // Use the monitor at the centre of the primary display, or override via env.
    let (mx, my) = std::env::var("WFINFO_MONITOR_POINT")
        .ok()
        .and_then(|s| {
            let parts: Vec<i32> = s.split(',').filter_map(|p| p.trim().parse().ok()).collect();
            if parts.len() == 2 {
                Some((parts[0], parts[1]))
            } else {
                None
            }
        })
        .unwrap_or((1920, 720)); // default: centre of a typical 1920×1440 secondary monitor
    let warframe_window = Monitor::from_point(mx, my)
        .unwrap_or_else(|_| Monitor::all().unwrap().into_iter().next().unwrap());

    debug!(
        "Capture source resolution: {:?}x{:?}",
        warframe_window.width(),
        warframe_window.height()
    );
    let _ = window_name; // no longer used — kept for CLI compat

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
        run_detection(warframe_window, &db, &owned);
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
