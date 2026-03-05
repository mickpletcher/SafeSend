"""
SafeSend Document Downloader

Downloads documents from time-limited SAS URLs provided in webhook payloads.

CRITICAL: SAS URLs expire quickly. Always download immediately when you receive
the webhook. Never store a SAS URL for later use.
"""

import logging
import os
import asyncio
import httpx
from pathlib import Path

from .config import settings

logger = logging.getLogger("safesend.downloader")


async def download_document(
    sas_url: str,
    file_name: str,
    sub_dir: str = "",
    max_retries: int = 3,
) -> str:
    """
    Download a document from a SafeSend SAS URL and save it locally.

    Args:
        sas_url:     The time-limited Azure SAS URL from the webhook payload.
        file_name:   Desired filename for the saved document.
        sub_dir:     Subdirectory under DOWNLOAD_BASE_PATH to store the file.
        max_retries: Number of download attempts before raising an exception.

    Returns:
        Absolute path to the saved file.

    Raises:
        Exception if all retry attempts fail.
    """
    if not sas_url:
        raise ValueError("sas_url is empty - no document to download")

    # Build the output path
    base_path = Path(settings.DOWNLOAD_BASE_PATH)
    if sub_dir:
        output_dir = base_path / sub_dir
    else:
        output_dir = base_path

    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize the filename
    safe_name = _sanitize_filename(file_name)
    output_path = output_dir / safe_name

    # Avoid re-downloading the same file
    if output_path.exists():
        logger.info(f"File already exists, skipping download: {output_path}")
        return str(output_path)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(sas_url)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)

            file_size_kb = output_path.stat().st_size / 1024
            logger.info(
                f"Downloaded: {safe_name} ({file_size_kb:.1f} KB) -> {output_path}"
            )
            return str(output_path)

        except httpx.HTTPStatusError as exc:
            last_error = exc
            logger.warning(
                f"Download attempt {attempt}/{max_retries} failed | "
                f"status={exc.response.status_code} | file={safe_name}"
            )
            if exc.response.status_code in (403, 404):
                # SAS URL expired or invalid - no point retrying
                logger.error(
                    f"SAS URL is expired or invalid for {safe_name}. "
                    f"Cannot recover - URL must be used immediately after receiving the webhook."
                )
                raise

        except Exception as exc:
            last_error = exc
            logger.warning(
                f"Download attempt {attempt}/{max_retries} failed | "
                f"error={exc} | file={safe_name}"
            )

        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s

    raise Exception(
        f"All {max_retries} download attempts failed for {safe_name}: {last_error}"
    )


def _sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in file paths."""
    if not name:
        return "document.bin"

    # Replace path separators and null bytes
    for char in r'\/|:*?"<>':
        name = name.replace(char, "_")

    # Collapse multiple underscores
    while "__" in name:
        name = name.replace("__", "_")

    return name.strip("_") or "document.bin"
