"""Polite JobThai scraper package (discovery, fetch, parse, quota, staging, rediscovery)."""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "ALLOWED_SOURCES": ("pipeline.scraper.config", "ALLOWED_SOURCES"),
    "FORBIDDEN_SOURCES": ("pipeline.scraper.config", "FORBIDDEN_SOURCES"),
    "MIN_DELAY_SEC": ("pipeline.scraper.config", "MIN_DELAY_SEC"),
    "ForbiddenSourceError": ("pipeline.scraper.config", "ForbiddenSourceError"),
    "enforce_delay": ("pipeline.scraper.config", "enforce_delay"),
    "validate_source": ("pipeline.scraper.config", "validate_source"),
    "validate_url": ("pipeline.scraper.config", "validate_url"),
    "build_discovery_targets": ("pipeline.scraper.discovery", "build_discovery_targets"),
    "discover_targets": ("pipeline.scraper.discovery", "discover_targets"),
    "extract_listing_ids": ("pipeline.scraper.discovery", "extract_listing_ids"),
    "detect_block_reason": ("pipeline.scraper.fetch", "detect_block_reason"),
    "fetch_jobs": ("pipeline.scraper.fetch", "fetch_jobs"),
    "StagingStore": ("pipeline.scraper.load_staging", "StagingStore"),
    "load_raw_directory": ("pipeline.scraper.load_staging", "load_raw_directory"),
    "parse_file": ("pipeline.scraper.parse", "parse_file"),
    "parse_html": ("pipeline.scraper.parse", "parse_html"),
    "scrub_pii": ("pipeline.scraper.parse", "scrub_pii"),
    "strip_hr_contacts": ("pipeline.scraper.parse", "strip_hr_contacts"),
    "compute_stratified_quota": ("pipeline.scraper.quota", "compute_stratified_quota"),
    "load_province_totals": ("pipeline.scraper.quota", "load_province_totals"),
    "select_stratified_sample": ("pipeline.scraper.quota", "select_stratified_sample"),
    "verify_weight_conservation": ("pipeline.scraper.quota", "verify_weight_conservation"),
    "run_weekly_rediscovery": ("pipeline.scraper.rediscover", "run_weekly_rediscovery"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        mod_name, attr_name = _EXPORTS[name]
        mod = import_module(mod_name)
        val = getattr(mod, attr_name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
