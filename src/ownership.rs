use std::collections::HashMap;
use std::fs::read_to_string;
use std::io;
use std::path::Path;
use std::process::Command;

use log::{info, warn};
use serde::Deserialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ownership {
    Owned(u32),
    Need,
    Unknown,
}

impl Ownership {
    pub fn label(&self) -> String {
        match self {
            Ownership::Owned(n) => format!("OWNED x{}", n),
            Ownership::Need     => "NEED".to_string(),
            Ownership::Unknown  => "UNKNOWN".to_string(),
        }
    }

    pub fn colored(&self) -> String {
        match self {
            Ownership::Owned(n) => format!("\x1b[2mOWNED x{}\x1b[0m", n),
            Ownership::Need     => "\x1b[1;32mNEED\x1b[0m".to_string(),
            Ownership::Unknown  => "\x1b[33mUNKNOWN\x1b[0m".to_string(),
        }
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(transparent)]
pub struct OwnedDb {
    items: HashMap<String, u32>,
}

impl OwnedDb {
    pub fn load(path: &Path) -> io::Result<Self> {
        let text = read_to_string(path)?;
        let items: HashMap<String, u32> = serde_json::from_str(&text)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        info!("Loaded ownership: {} entries from {}", items.len(), path.display());
        Ok(OwnedDb { items })
    }

    pub fn load_or_empty(path: &Path) -> Self {
        match Self::load(path) {
            Ok(db) => db,
            Err(e) => {
                warn!(
                    "No ownership file at {} ({}). All items will show UNKNOWN.",
                    path.display(),
                    e
                );
                OwnedDb::default()
            }
        }
    }

    pub fn lookup(&self, drop_name: &str) -> Ownership {
        match self.items.get(drop_name) {
            None         => Ownership::Unknown,
            Some(0)      => Ownership::Need,
            Some(&n)     => Ownership::Owned(n),
        }
    }
}

pub fn notify(title: &str, body: &str, urgency: &str) {
    // --transient: don't steal focus or persist in notification centre
    // --hint=int:transient:1: extra hint for notification daemons that need it
    let _ = Command::new("notify-send")
        .args([
            "--app-name=wfinfo",
            "--urgency", urgency,
            "--expire-time=4500",
            "--transient",
            "--hint=int:transient:1",
            title, body,
        ])
        .spawn();
}
