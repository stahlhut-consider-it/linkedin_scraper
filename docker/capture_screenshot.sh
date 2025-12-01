#!/usr/bin/env bash
set -euo pipefail

OUTPUT_PATH="${1:-/tmp/linkedin_scraper_screen.png}"
DISPLAY_TO_USE="${DISPLAY:-:99}"

import -display "${DISPLAY_TO_USE}" -window root "${OUTPUT_PATH}"
echo "Screenshot saved to ${OUTPUT_PATH}"
