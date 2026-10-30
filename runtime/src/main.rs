mod supervise;
mod tor;

use anyhow::{bail, Context, Result};

#[tokio::main(worker_threads = 2)]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,arti_client=warn,tor_=warn".into()),
        )
        .init();
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("supervise") => {
            let path = args.get(2).context("supervise requires a config path")?;
            let config = supervise::Config::parse(&std::fs::read_to_string(path)?, "prod")?;
            supervise::run(config, shutdown()).await
        }
        Some("tor") => tor::run().await,
        _ => bail!("usage: autolycus-runtime supervise CONFIG | tor"),
    }
}

async fn shutdown() {
    use tokio::signal::unix::{signal, SignalKind};
    let mut term = signal(SignalKind::terminate()).expect("register SIGTERM");
    tokio::select! {
        _ = term.recv() => {},
        _ = tokio::signal::ctrl_c() => {},
    }
}
