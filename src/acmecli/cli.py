from pathlib import Path
import logging
import os
import concurrent.futures
from typing import Optional, Dict, Any
from .types import ReportRow, MetricValue
from .reporter import write_ndjson
from .metrics.base import REGISTRY
from .github_handler import GitHubHandler
from .hf_handler import HFHandler
from .cache import InMemoryCache
from .scoring import compute_net_score

logger = logging.getLogger(__name__)


def setup_logging():
    log_file = os.environ.get("LOG_FILE")
    raw_level = os.environ.get("LOG_LEVEL", "0")
    try:
        log_level = int(raw_level)
    except ValueError:
        log_level = 0

    level_map = {
        0: logging.CRITICAL + 1,
        1: logging.INFO,
        2: logging.DEBUG,
    }
    level = level_map.get(log_level, logging.ERROR)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch()
        handler = logging.FileHandler(log_path, encoding="utf-8")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    if log_level == 0:
        handler.setLevel(logging.CRITICAL + 1)
    else:
        handler.setLevel(level)
    root_logger.addHandler(handler)


def classify(url: str) -> str:
    u = url.strip().lower()
    if "huggingface.co/datasets/" in u:
        return "DATASET"
    if "github.com/" in u:
        return "MODEL_GITHUB"
    if "huggingface.co/" in u:
        return "MODEL_HF"
    return "CODE"


def extract_urls(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def get_metric_value(results: Dict[str, MetricValue], name: str, default: float = 0.0) -> float:
    """Safely get metric value from results dictionary."""
    metric = results.get(name)
    return metric.value if metric else default


def get_metric_latency(results: Dict[str, MetricValue], name: str, default: int = 0) -> int:
    """Safely get metric latency from results dictionary."""
    metric = results.get(name)
    return metric.latency_ms if metric else default


def process_url(url: str, github_handler: GitHubHandler, hf_handler: HFHandler, cache: InMemoryCache) -> Optional[ReportRow]:
    if classify(url) == "MODEL_GITHUB":
        repo_name = url.split("/")[-1]
        meta = github_handler.fetch_meta(url)
    elif classify(url) == "MODEL_HF":
        repo_name = url.split("/")[-1]
        meta = hf_handler.fetch_meta(url)
    else:
        return None

    if not meta:
        return None

    results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_metric = {executor.submit(m.score, meta): m.name for m in REGISTRY}
        for future in concurrent.futures.as_completed(future_to_metric):
            metric_name = future_to_metric[future]
            try:
                mv = future.result()
                results[metric_name] = mv
            except Exception as e:
                logger.error(f"Error computing metric {metric_name}: {e}", exc_info=True)
                # Create a default MetricValue for failed metrics
                results[metric_name] = MetricValue(metric_name, 0.0, 0)

    net_score, net_score_latency = compute_net_score(results)

    # Handle size_score specially since it returns a dict
    size_result = results.get("size_score")
    size_score_value = (
        size_result.value
        if size_result
        else {
            "raspberry_pi": 0.0,
            "jetson_nano": 0.0,
            "desktop_pc": 0.0,
            "aws_server": 0.0,
        }
    )

    return ReportRow(
        name=repo_name,
        category="MODEL",
        net_score=net_score,
        net_score_latency=net_score_latency,
        ramp_up_time=get_metric_value(results, "ramp_up_time"),
        ramp_up_time_latency=get_metric_latency(results, "ramp_up_time"),
        bus_factor=get_metric_value(results, "bus_factor"),
        bus_factor_latency=get_metric_latency(results, "bus_factor"),
        performance_claims=get_metric_value(results, "performance_claims"),
        performance_claims_latency=get_metric_latency(results, "performance_claims"),
        license=get_metric_value(results, "license"),
        license_latency=get_metric_latency(results, "license"),
        size_score=size_score_value,
        size_score_latency=get_metric_latency(results, "size_score"),
        dataset_and_code_score=get_metric_value(results, "dataset_and_code_score"),
        dataset_and_code_score_latency=get_metric_latency(results, "dataset_and_code_score"),
        dataset_quality=get_metric_value(results, "dataset_quality"),
        dataset_quality_latency=get_metric_latency(results, "dataset_quality"),
        code_quality=get_metric_value(results, "code_quality"),
        code_quality_latency=get_metric_latency(results, "code_quality"),
        reproducibility=get_metric_value(results, "reproducibility"),
        reproducibility_latency=get_metric_latency(results, "reproducibility"),
        reviewedness=get_metric_value(results, "reviewedness"),
        reviewedness_latency=get_metric_latency(results, "reviewedness"),
        treescore=get_metric_value(results, "treescore"),
        treescore_latency=get_metric_latency(results, "treescore"),
        llm_summary=get_metric_value(results, "LLMSummary"),
        llm_summary_latency=get_metric_latency(results, "LLMSummary"),
    )


def main(argv: list[str]) -> int:
    setup_logging()
    
    # Find URL file - either after "score" or last argument
    url_file: Optional[str] = None
    if "score" in argv:
        score_idx = argv.index("score")
        if score_idx + 1 < len(argv):
            url_file = argv[score_idx + 1]
    
    if not url_file:
        url_file = argv[-1] if len(argv) > 0 else None
    
    if not url_file or not Path(url_file).exists():
        print(f"Error: URL file not found: {url_file}")
        print("Usage: run score <URL_FILE>")
        return 1
    github_handler = GitHubHandler()
    hf_handler = HFHandler()
    cache = InMemoryCache()
    lines = Path(url_file).read_text(encoding="utf-8").splitlines()
    for raw in lines:
        for url in extract_urls(raw):
            kind = classify(url)
            logger.debug("Classified URL %s as %s", url, kind)
            if kind not in {"MODEL_GITHUB", "MODEL_HF"}:
                logger.debug("Skipping unsupported URL: %s", url)
                continue
            logger.info("Processing URL: %s", url)
            row = process_url(url, github_handler, hf_handler, cache)
            if row:
                logger.info("Emitted report for %s", row.name)
                write_ndjson(row)
            else:
                logger.debug("No report produced for %s", url)
    return 0
