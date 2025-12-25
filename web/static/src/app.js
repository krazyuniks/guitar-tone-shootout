// Flowbite components (import from CDN or local)
// For local: npm install flowbite, then import 'flowbite';
// For now, we'll use CDN in templates

// HTMX event handlers
document.addEventListener('htmx:afterSwap', (event) => {
    // Reinitialize Flowbite components after HTMX swaps content
    if (typeof initFlowbite === 'function') {
        initFlowbite();
    }
});

// Signal chain builder
const SignalChainBuilder = {
    chain: [],

    addBlock(type, value) {
        this.chain.push({ type, value });
        this.render();
    },

    removeBlock(index) {
        this.chain.splice(index, 1);
        this.render();
    },

    moveBlock(fromIndex, toIndex) {
        const [block] = this.chain.splice(fromIndex, 1);
        this.chain.splice(toIndex, 0, block);
        this.render();
    },

    render() {
        const container = document.getElementById('signal-chain-preview');
        if (!container) return;

        container.innerHTML = this.chain.map((block, index) => `
            <div class="signal-block" data-index="${index}">
                <div class="text-xs uppercase tracking-wider text-slate-400 mb-1">${block.type}</div>
                <div class="font-semibold">${block.value}</div>
                <button onclick="SignalChainBuilder.removeBlock(${index})" class="mt-2 text-red-400 hover:text-red-300 text-sm">
                    Remove
                </button>
            </div>
            ${index < this.chain.length - 1 ? '<div class="text-2xl text-red-500">→</div>' : ''}
        `).join('');
    },

    toINI() {
        // Convert chain to INI format for form submission
        return this.chain;
    }
};

// Expose to global scope for HTMX and inline handlers
window.SignalChainBuilder = SignalChainBuilder;

// Form validation
function validateComparisonForm(form) {
    const name = form.querySelector('[name="name"]');
    const diTracks = form.querySelectorAll('[name="di_tracks[]"]');
    const amps = form.querySelectorAll('[name="amps[]"]');
    const cabs = form.querySelectorAll('[name="cabs[]"]');

    if (!name.value.trim()) {
        alert('Please enter a comparison name');
        return false;
    }

    if (diTracks.length === 0) {
        alert('Please add at least one DI track');
        return false;
    }

    if (amps.length === 0) {
        alert('Please add at least one amp');
        return false;
    }

    if (cabs.length === 0) {
        alert('Please add at least one cabinet IR');
        return false;
    }

    return true;
}

window.validateComparisonForm = validateComparisonForm;
