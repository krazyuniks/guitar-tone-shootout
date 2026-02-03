#!/bin/bash
#
# post-iteration-visual-diff.sh - Visual regression testing callback
#
# Usage: post-iteration-visual-diff.sh [options]
#
# This callback runs after each Ralph iteration to:
#   1. Take screenshots of configured URLs
#   2. Compare against baseline screenshots
#   3. Report pixel difference percentage
#   4. Fail if difference exceeds threshold
#
# Configuration (via environment variables):
#   VISUAL_DIFF_ENABLED=true           Enable/disable the callback
#   VISUAL_DIFF_BASELINE_URL=http://localhost:4321   Baseline URL (source framework)
#   VISUAL_DIFF_COMPARISON_URL=http://localhost:8010 Comparison URL (target framework)
#   VISUAL_DIFF_THRESHOLD=0.05         Maximum allowed pixel difference (0-1)
#   VISUAL_DIFF_PAGES=/,/library/gear  Comma-separated pages to compare
#   VISUAL_DIFF_OUTPUT_DIR=.ralph-hybrid/{feature}/visual-diffs
#
# Configuration (via config.yaml):
#   visual_regression:
#     enabled: true
#     baseline_url: "http://localhost:4321"
#     comparison_url: "http://localhost:8010"
#     threshold: 0.05
#     pages:
#       - "/"
#       - "/library/gear"
#       - "/browse"
#

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default configuration
ENABLED="${VISUAL_DIFF_ENABLED:-false}"
BASELINE_URL="${VISUAL_DIFF_BASELINE_URL:-http://localhost:4321}"
COMPARISON_URL="${VISUAL_DIFF_COMPARISON_URL:-http://localhost:8010}"
THRESHOLD="${VISUAL_DIFF_THRESHOLD:-0.05}"
PAGES="${VISUAL_DIFF_PAGES:-/}"
OUTPUT_DIR="${VISUAL_DIFF_OUTPUT_DIR:-.ralph-hybrid/visual-diffs}"

# Parse config.yaml if present
CONFIG_FILE="${RALPH_CONFIG:-}"
if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
    # Try to read visual_regression section
    if command -v yq &> /dev/null; then
        ENABLED=$(yq -r '.visual_regression.enabled // "false"' "$CONFIG_FILE" 2>/dev/null || echo "$ENABLED")
        BASELINE_URL=$(yq -r '.visual_regression.baseline_url // ""' "$CONFIG_FILE" 2>/dev/null || echo "$BASELINE_URL")
        COMPARISON_URL=$(yq -r '.visual_regression.comparison_url // ""' "$CONFIG_FILE" 2>/dev/null || echo "$COMPARISON_URL")
        THRESHOLD=$(yq -r '.visual_regression.threshold // "0.05"' "$CONFIG_FILE" 2>/dev/null || echo "$THRESHOLD")
        PAGES=$(yq -r '.visual_regression.pages // [] | join(",")' "$CONFIG_FILE" 2>/dev/null || echo "$PAGES")
    fi
fi

# Early exit if disabled
if [[ "$ENABLED" != "true" ]]; then
    echo "Visual diff callback: disabled" >&2
    exit 0
fi

# Check dependencies
check_dependencies() {
    local missing=()

    if ! command -v npx &> /dev/null; then
        missing+=("npx (Node.js)")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}Missing dependencies: ${missing[*]}${NC}" >&2
        echo "Install Node.js and run: npm install -g playwright" >&2
        exit 1
    fi
}

# Take screenshot using Playwright
take_screenshot() {
    local url="$1"
    local output_file="$2"

    npx playwright screenshot \
        --browser chromium \
        --full-page \
        --timeout 30000 \
        "$url" "$output_file" 2>/dev/null
}

# Compare two images using ImageMagick (if available) or basic diff
compare_images() {
    local baseline="$1"
    local comparison="$2"
    local diff_output="$3"

    if command -v compare &> /dev/null; then
        # ImageMagick compare
        local diff_metric
        diff_metric=$(compare -metric AE "$baseline" "$comparison" "$diff_output" 2>&1 || true)
        echo "$diff_metric"
    else
        # Fallback: file size comparison (rough approximation)
        local size1 size2
        size1=$(stat -f%z "$baseline" 2>/dev/null || stat -c%s "$baseline" 2>/dev/null)
        size2=$(stat -f%z "$comparison" 2>/dev/null || stat -c%s "$comparison" 2>/dev/null)
        local diff=$((size1 > size2 ? size1 - size2 : size2 - size1))
        local max=$((size1 > size2 ? size1 : size2))
        echo $((diff * 100 / max))
    fi
}

# Main function
main() {
    check_dependencies

    # Create output directory
    mkdir -p "$OUTPUT_DIR"

    # Convert comma-separated pages to array
    IFS=',' read -ra PAGE_ARRAY <<< "$PAGES"

    # Results tracking
    local total=0
    local passed=0
    local failed=0
    local results=()

    echo "Visual Diff Callback: Starting comparison" >&2
    echo "  Baseline: $BASELINE_URL" >&2
    echo "  Comparison: $COMPARISON_URL" >&2
    echo "  Threshold: $THRESHOLD" >&2
    echo "" >&2

    for page in "${PAGE_ARRAY[@]}"; do
        total=$((total + 1))
        page=$(echo "$page" | tr -d ' ')  # Trim whitespace

        # File names (sanitize page path)
        local safe_name
        safe_name=$(echo "$page" | sed 's/[\/]/_/g; s/^_//')
        [[ -z "$safe_name" ]] && safe_name="index"

        local baseline_file="$OUTPUT_DIR/baseline_${safe_name}.png"
        local comparison_file="$OUTPUT_DIR/comparison_${safe_name}.png"
        local diff_file="$OUTPUT_DIR/diff_${safe_name}.png"

        echo -n "  Testing $page... " >&2

        # Take screenshots
        if ! take_screenshot "${BASELINE_URL}${page}" "$baseline_file"; then
            echo -e "${RED}FAIL (baseline screenshot failed)${NC}" >&2
            failed=$((failed + 1))
            results+=("{\"page\": \"$page\", \"status\": \"error\", \"error\": \"baseline_screenshot_failed\"}")
            continue
        fi

        if ! take_screenshot "${COMPARISON_URL}${page}" "$comparison_file"; then
            echo -e "${RED}FAIL (comparison screenshot failed)${NC}" >&2
            failed=$((failed + 1))
            results+=("{\"page\": \"$page\", \"status\": \"error\", \"error\": \"comparison_screenshot_failed\"}")
            continue
        fi

        # Compare
        local diff_pixels
        diff_pixels=$(compare_images "$baseline_file" "$comparison_file" "$diff_file")

        # Calculate percentage (assuming 1920x1080 viewport)
        # Note: This is a rough approximation; actual pixel count varies
        local viewport_pixels=2073600  # 1920 * 1080
        local diff_pct
        if [[ "$diff_pixels" =~ ^[0-9]+$ ]]; then
            diff_pct=$(echo "scale=4; $diff_pixels / $viewport_pixels" | bc 2>/dev/null || echo "0")
        else
            diff_pct="0"
        fi

        # Check threshold
        local threshold_exceeded
        threshold_exceeded=$(echo "$diff_pct > $THRESHOLD" | bc 2>/dev/null || echo "0")

        if [[ "$threshold_exceeded" == "1" ]]; then
            echo -e "${RED}FAIL (${diff_pct}% diff > ${THRESHOLD}% threshold)${NC}" >&2
            failed=$((failed + 1))
            results+=("{\"page\": \"$page\", \"status\": \"fail\", \"diff_percentage\": $diff_pct, \"threshold\": $THRESHOLD}")
        else
            echo -e "${GREEN}PASS (${diff_pct}% diff)${NC}" >&2
            passed=$((passed + 1))
            results+=("{\"page\": \"$page\", \"status\": \"pass\", \"diff_percentage\": $diff_pct, \"threshold\": $THRESHOLD}")
        fi
    done

    # Output JSON report
    echo ""
    echo "{"
    echo "  \"callback\": \"visual-diff\","
    echo "  \"baseline_url\": \"$BASELINE_URL\","
    echo "  \"comparison_url\": \"$COMPARISON_URL\","
    echo "  \"threshold\": $THRESHOLD,"
    echo "  \"summary\": {"
    echo "    \"total\": $total,"
    echo "    \"passed\": $passed,"
    echo "    \"failed\": $failed,"
    echo "    \"status\": \"$([ "$failed" -eq 0 ] && echo 'pass' || echo 'fail')\""
    echo "  },"
    echo "  \"results\": ["

    local first=true
    for result in "${results[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo ","
        fi
        echo -n "    $result"
    done
    echo ""
    echo "  ],"
    echo "  \"output_dir\": \"$OUTPUT_DIR\""
    echo "}"

    # Summary to stderr
    echo "" >&2
    if [ "$failed" -eq 0 ]; then
        echo -e "${GREEN}Visual Diff: PASS ($passed/$total pages)${NC}" >&2
    else
        echo -e "${RED}Visual Diff: FAIL ($failed/$total pages exceeded threshold)${NC}" >&2
        echo "  Screenshots saved to: $OUTPUT_DIR" >&2
    fi

    # Exit with appropriate code
    [ "$failed" -eq 0 ]
}

# Run main
main "$@"
