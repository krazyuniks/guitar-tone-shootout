# Web Development Skill

Use this skill when working on the `web/` subproject.

## Context

The web interface is a Flask + HTMX application for building and managing comparisons.

## Key Technologies

- **Flask**: Python web framework (server-side rendering)
- **HTMX**: Dynamic interactions without heavy JavaScript
- **Tailwind CSS 4**: Utility-first CSS framework
- **Flowbite**: Tailwind component library
- **pnpm**: Fast, disk-efficient package manager

## Architecture

```
Flask App
    ├── templates/           # Jinja2 templates
    │   ├── base.html       # Base layout with Tailwind/Flowbite
    │   ├── index.html      # Home page
    │   └── partials/       # HTMX partial responses
    ├── static/
    │   ├── src/            # Source CSS/JS
    │   └── dist/           # Built assets
    └── app/
        └── main.py         # Flask routes
```

## Key Patterns

### Flask Route with HTMX
```python
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/comparisons")
def list_comparisons():
    comparisons = get_all_comparisons()
    if request.headers.get("HX-Request"):
        return render_template("partials/comparison_list.html", comparisons=comparisons)
    return render_template("comparisons.html", comparisons=comparisons)
```

### HTMX Partial
```html
<!-- templates/partials/comparison_list.html -->
{% for c in comparisons %}
<tr class="border-b hover:bg-gray-50">
    <td class="px-6 py-4">{{ c.name }}</td>
    <td class="px-6 py-4">
        <button hx-delete="/comparisons/{{ c.id }}"
                hx-confirm="Delete {{ c.name }}?"
                hx-target="closest tr"
                hx-swap="outerHTML"
                class="text-red-600 hover:text-red-800">
            Delete
        </button>
    </td>
</tr>
{% endfor %}
```

### Tailwind + Flowbite Component
```html
<!-- Button with Flowbite styling -->
<button type="button"
        class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4
               focus:ring-blue-300 font-medium rounded-lg text-sm
               px-5 py-2.5 dark:bg-blue-600 dark:hover:bg-blue-700
               focus:outline-none dark:focus:ring-blue-800">
    Create Comparison
</button>
```

## Development Commands

```bash
cd web
pnpm install              # Install Node dependencies
pnpm dev                  # Watch mode for Tailwind
just serve-dev            # Run Flask dev server
just build                # Build production assets
```

## Build Pipeline

1. **Tailwind**: Compiles `static/src/styles.css` → `static/dist/styles.css`
2. **esbuild**: Bundles `static/src/app.js` → `static/dist/app.js`
3. **Flask**: Serves built assets from `static/dist/`

## Common Issues

1. **Styles not updating**: Run `pnpm build` or ensure watch mode is running
2. **HTMX not working**: Check CDN is loaded in base.html
3. **Flowbite components broken**: Ensure Flowbite JS is initialized
