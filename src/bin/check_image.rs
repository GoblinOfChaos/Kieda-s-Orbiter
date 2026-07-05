use std::path::PathBuf;

use clap::Parser;
use image::io::Reader;
use wfinfo::{
    database::Database,
    ocr::{normalize_string, reward_image_to_reward_names},
    ownership::{OwnedDb, Ownership},
};

#[derive(Parser)]
struct Args {
    screenshot: PathBuf,
    #[arg(default_value = "owned_items.json")]
    owned: PathBuf,
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().filter_or("WFINFO_LOG", "info"))
        .init();

    let args = Args::parse();
    let image = Reader::open(&args.screenshot)
        .expect("could not open screenshot")
        .decode()
        .expect("could not decode screenshot");

    let db = Database::load_from_file(None, None);
    let owned = OwnedDb::load_or_empty(&args.owned);

    let names: Vec<String> = reward_image_to_reward_names(image, None)
        .iter()
        .map(|s| normalize_string(s))
        .collect();

    println!("Raw OCR results:");
    for n in &names {
        println!("  {:?}", n);
    }
    println!();
    println!("Resolved + ownership:");
    for n in &names {
        match db.find_item(n, None) {
            Some(item) => {
                let own = owned.lookup(&item.drop_name);
                println!("  {:<40}  {}", item.drop_name, own.colored());
            }
            None => {
                println!(
                    "  {:<40}  {}",
                    format!("? {}", n),
                    Ownership::Unknown.colored()
                );
            }
        }
    }
}
