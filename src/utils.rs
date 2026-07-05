use reqwest::StatusCode;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

/// Local fallback paths relative to the project root (where the binary lives).
fn local_fallback(filename: &str) -> Option<PathBuf> {
    // Try next to the binary first, then the cwd.
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()));
    for base in exe_dir
        .into_iter()
        .chain(std::iter::once(std::env::current_dir().unwrap_or_default()))
    {
        let candidate = base.join(filename);
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

pub fn fetch_prices_and_items() -> Result<(PathBuf, PathBuf), anyhow::Error> {
    let prices = download_and_save("https://api.warframestat.us/wfinfo/prices/", "prices.json")?;
    let items = download_and_save(
        "https://api.warframestat.us/wfinfo/filtered_items/",
        "filtered_items.json",
    )?;
    Ok((prices, items))
}

fn download_and_save(url: &str, filename: &str) -> Result<PathBuf, anyhow::Error> {
    let tmp_path = std::env::temp_dir().join(filename);
    if tmp_path.exists() {
        return Ok(tmp_path);
    }

    let res = reqwest::blocking::get(url)?;
    if res.status() == StatusCode::OK {
        let mut file = OpenOptions::new()
            .write(true)
            .truncate(true)
            .create(true)
            .open(&tmp_path)?;
        file.write_all(res.text()?.as_bytes())?;
        return Ok(tmp_path);
    }

    // API returned non-200 (e.g. 503). Fall back to local project file.
    let status = res.status();
    if let Some(local) = local_fallback(filename) {
        eprintln!(
            "Warning: {} returned {}. Using local fallback: {}",
            url,
            status,
            local.display()
        );
        return Ok(local);
    }

    anyhow::bail!(
        "Failed to download {} (HTTP {}) and no local fallback found for {}",
        url,
        status,
        filename
    )
}
