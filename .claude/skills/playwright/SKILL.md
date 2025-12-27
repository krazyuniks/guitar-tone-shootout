# Playwright Skill

**Activation:** E2E testing, browser automation, debugging, screenshots

## Overview

Playwright is used for:
1. **E2E Testing** - Frontend integration tests
2. **Pipeline Rendering** - HTML to PNG for comparison images
3. **Debugging** - Visual browser automation

## MCP Integration

This project has Playwright MCP available. Use `mcp__playwright__*` tools for browser automation:

### Navigation
```
mcp__playwright__browser_navigate - Go to URL
mcp__playwright__browser_navigate_back - Go back
mcp__playwright__browser_snapshot - Get page accessibility tree (preferred over screenshot)
mcp__playwright__browser_take_screenshot - Capture screenshot
```

### Interaction
```
mcp__playwright__browser_click - Click element
mcp__playwright__browser_type - Type text
mcp__playwright__browser_fill_form - Fill multiple fields
mcp__playwright__browser_select_option - Select dropdown option
mcp__playwright__browser_hover - Hover over element
mcp__playwright__browser_press_key - Press keyboard key
```

### Debugging
```
mcp__playwright__browser_console_messages - Get console logs
mcp__playwright__browser_network_requests - Get network requests
mcp__playwright__browser_evaluate - Run JavaScript
```

## Debugging Workflow

### 1. Visual Debugging

```
# Take snapshot first (shows element refs)
Use mcp__playwright__browser_snapshot

# Identify element by ref from snapshot
Use mcp__playwright__browser_click with ref="element-ref"

# Check console for errors
Use mcp__playwright__browser_console_messages
```

### 2. Network Debugging

```
# Get all network requests
Use mcp__playwright__browser_network_requests

# Filter for API calls
Use mcp__playwright__browser_network_requests with includeStatic=false
```

### 3. JavaScript Debugging

```
# Run arbitrary JS
Use mcp__playwright__browser_evaluate with function="() => document.title"

# Check element state
Use mcp__playwright__browser_evaluate with function="(el) => el.value" and element ref
```

## E2E Test Patterns (Python)

### Test Setup

```python
# tests/e2e/conftest.py
import pytest
from playwright.async_api import async_playwright, Page, Browser

@pytest.fixture
async def browser() -> Browser:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()

@pytest.fixture
async def page(browser: Browser) -> Page:
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()

@pytest.fixture
async def authenticated_page(page: Page, test_user: User) -> Page:
    """Page with logged-in user session."""
    await page.goto(f"{BASE_URL}/login")
    await page.fill('[name="username"]', test_user.username)
    await page.fill('[name="password"]', test_user.password)
    await page.click('button[type="submit"]')
    await page.wait_for_url("**/dashboard")
    return page
```

### Page Object Pattern

```python
# tests/e2e/pages/dashboard.py
from playwright.async_api import Page

class DashboardPage:
    def __init__(self, page: Page):
        self.page = page
        self.shootout_list = page.locator('[data-testid="shootout-list"]')
        self.create_button = page.get_by_role("button", name="Create Shootout")

    async def goto(self):
        await self.page.goto(f"{BASE_URL}/dashboard")

    async def create_shootout(self, title: str) -> None:
        await self.create_button.click()
        await self.page.fill('[name="title"]', title)
        await self.page.click('button[type="submit"]')

    async def get_shootout_count(self) -> int:
        return await self.shootout_list.locator('[data-testid="shootout-item"]').count()
```

### Test Example

```python
# tests/e2e/test_shootouts.py
import pytest
from tests.e2e.pages.dashboard import DashboardPage

@pytest.mark.asyncio
async def test_create_shootout(authenticated_page: Page):
    """User can create a new shootout."""
    dashboard = DashboardPage(authenticated_page)
    await dashboard.goto()

    initial_count = await dashboard.get_shootout_count()

    await dashboard.create_shootout("Test Tone Comparison")

    # Wait for new item to appear
    await authenticated_page.wait_for_selector('[data-testid="shootout-item"]')

    final_count = await dashboard.get_shootout_count()
    assert final_count == initial_count + 1
```

## Assertions

```python
from playwright.async_api import expect

# Visibility
await expect(page.locator(".error")).to_be_visible()
await expect(page.locator(".loading")).to_be_hidden()

# Text content
await expect(page.locator("h1")).to_have_text("Dashboard")
await expect(page.locator(".message")).to_contain_text("Success")

# Attributes
await expect(page.locator("input")).to_have_value("test@example.com")
await expect(page.locator("button")).to_be_disabled()

# URL
await expect(page).to_have_url("**/dashboard")
```

## Locator Strategies (Priority Order)

1. **Role-based** (most resilient)
   ```python
   page.get_by_role("button", name="Submit")
   page.get_by_role("heading", name="Dashboard")
   page.get_by_role("textbox", name="Email")
   ```

2. **Test ID** (explicit, stable)
   ```python
   page.get_by_test_id("shootout-list")
   page.locator('[data-testid="create-button"]')
   ```

3. **Label/Placeholder** (user-facing)
   ```python
   page.get_by_label("Email")
   page.get_by_placeholder("Enter your email")
   ```

4. **CSS Selectors** (last resort)
   ```python
   page.locator(".submit-btn")
   page.locator("#main-form input[type='email']")
   ```

## Pipeline Rendering

For generating comparison images in the pipeline:

```python
# pipeline/src/guitar_tone_shootout/render.py
from playwright.async_api import async_playwright

async def render_comparison_image(
    html_path: Path,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
) -> None:
    """Render HTML template to PNG image."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": width, "height": height})

        await page.goto(f"file://{html_path.absolute()}")
        await page.wait_for_load_state("networkidle")

        await page.screenshot(path=str(output_path), type="png")
        await browser.close()
```

## Debugging Tips

### Console Errors
```
# Via MCP
Use mcp__playwright__browser_console_messages with level="error"

# In Python
page.on("console", lambda msg: print(f"Console: {msg.text}"))
```

### Network Failures
```
# Via MCP
Use mcp__playwright__browser_network_requests

# In Python
page.on("requestfailed", lambda req: print(f"Failed: {req.url}"))
```

### Screenshots on Failure
```python
@pytest.fixture
async def page(browser: Browser, request):
    page = await browser.new_page()
    yield page
    if request.node.rep_call.failed:
        await page.screenshot(path=f"screenshots/{request.node.name}.png")
```

### Trace Recording
```python
context = await browser.new_context()
await context.tracing.start(screenshots=True, snapshots=True)

# ... run tests ...

await context.tracing.stop(path="trace.zip")
# Open with: npx playwright show-trace trace.zip
```

## Running E2E Tests

```bash
# All E2E tests
docker compose exec backend pytest tests/e2e/

# Specific test
docker compose exec backend pytest tests/e2e/test_shootouts.py -v

# With browser visible (local dev)
HEADLESS=false pytest tests/e2e/ -v

# Generate trace on failure
pytest tests/e2e/ --tracing=retain-on-failure
```
