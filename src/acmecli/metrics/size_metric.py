import time
from ..types import MetricValue
from .base import register


class SizeMetric:
    """Metric to assess model size compatibility with different hardware platforms."""
    name = "size_score"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Get repository size in KB
        repo_size_kb = meta.get('size', 0)

        # Heuristic size thresholds for different hardware (in KB)
        # Based on typical model sizes and hardware constraints
        thresholds = {
            'raspberry_pi': 100_000,    # ~100MB - very constrained
            'jetson_nano': 1_000_000,   # ~1GB - moderate constraints
            'desktop_pc': 10_000_000,   # ~10GB - good resources
            'aws_server': 50_000_000    # ~50GB - high resources
        }

        # Calculate compatibility scores for each platform
        scores = {}
        for platform, threshold in thresholds.items():
            if repo_size_kb == 0:
                # Unknown size - give moderate score
                scores[platform] = 0.5
            elif repo_size_kb <= threshold * 0.1:
                # Very small - excellent compatibility
                scores[platform] = 1.0
            elif repo_size_kb <= threshold * 0.5:
                # Small - good compatibility
                scores[platform] = 0.8
            elif repo_size_kb <= threshold:
                # At threshold - moderate compatibility
                scores[platform] = 0.6
            elif repo_size_kb <= threshold * 2:
                # Over threshold - poor compatibility
                scores[platform] = 0.3
            else:
                # Way over threshold - very poor compatibility
                scores[platform] = 0.1

        # Check README for size-related information
        readme_text = meta.get('readme_text', '').lower()
        if readme_text:
            # Look for explicit size mentions
            lightweight_keywords = [
                'lightweight', 'small', 'compact', 'efficient'
            ]
            if any(keyword in readme_text for keyword in lightweight_keywords):
                # Boost all scores slightly for models claiming to be lightweight
                for platform in scores:
                    scores[platform] = min(1.0, scores[platform] + 0.1)
            else:
                large_keywords = ['large', 'heavy', 'resource-intensive']
                if any(keyword in readme_text for keyword in large_keywords):
                    # Reduce scores for models explicitly stating they are large
                    for platform in scores:
                        scores[platform] = max(0.0, scores[platform] - 0.1)

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, scores, latency_ms)


register(SizeMetric())
