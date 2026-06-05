document.addEventListener('DOMContentLoaded', function () {

    // ── Apply saved preferences on load ──
    applyTheme(localStorage.getItem('theme') || 'light');
    applyFontSize(localStorage.getItem('fontsize') || 'normal');
    applyContrast(localStorage.getItem('contrast') === 'on');
    applyNoAnim(localStorage.getItem('noanim') === 'on');
    updateAccessButtons();

    // ── Complete lesson button ──
    const completeBtn = document.getElementById('completeBtn');
    if (completeBtn) {
        completeBtn.addEventListener('click', function () {
            const lessonId = this.dataset.lessonId;
            const nextUrl = this.dataset.nextUrl;
            const doneText = this.dataset.doneText || 'Выполнено!';

            fetch(`/lesson/${lessonId}/complete`, { method: 'POST' })
                .then(() => {
                    this.innerHTML = '<i class="fas fa-check me-2"></i>' + doneText;
                    this.classList.remove('btn-success');
                    this.classList.add('btn-secondary');
                    this.disabled = true;
                    if (nextUrl) {
                        setTimeout(() => { window.location.href = nextUrl; }, 600);
                    } else {
                        setTimeout(() => { window.location.reload(); }, 600);
                    }
                });
        });
    }

    // ── Quiz answer click ──
    document.querySelectorAll('.quiz-option').forEach(function (opt) {
        opt.addEventListener('click', function () {
            const name = this.querySelector('input').name;
            document.querySelectorAll(`.quiz-option input[name="${name}"]`).forEach(function (inp) {
                inp.closest('.quiz-option').classList.remove('selected');
            });
            this.classList.add('selected');
            this.querySelector('input').checked = true;
        });
    });
});

// ════════════════════════════════════════
// THEME
// ════════════════════════════════════════
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}

function setTheme(theme) {
    applyTheme(theme);
    updateAccessButtons();
}

// ════════════════════════════════════════
// FONT SIZE
// ════════════════════════════════════════
function applyFontSize(size) {
    document.documentElement.setAttribute('data-fontsize', size);
    localStorage.setItem('fontsize', size);
}

function setFontSize(size) {
    applyFontSize(size);
    updateAccessButtons();
}

// ════════════════════════════════════════
// HIGH CONTRAST
// ════════════════════════════════════════
function applyContrast(on) {
    document.documentElement.setAttribute('data-contrast', on ? 'on' : 'off');
    localStorage.setItem('contrast', on ? 'on' : 'off');
}

function toggleContrast() {
    const current = document.documentElement.getAttribute('data-contrast') === 'on';
    applyContrast(!current);
    updateAccessButtons();
}

// ════════════════════════════════════════
// NO ANIMATIONS
// ════════════════════════════════════════
function applyNoAnim(on) {
    document.documentElement.setAttribute('data-noanim', on ? 'on' : 'off');
    localStorage.setItem('noanim', on ? 'on' : 'off');
}

function toggleNoAnim() {
    const current = document.documentElement.getAttribute('data-noanim') === 'on';
    applyNoAnim(!current);
    updateAccessButtons();
}

// ════════════════════════════════════════
// ACCESSIBILITY PANEL
// ════════════════════════════════════════
function toggleAccessPanel() {
    const panel = document.getElementById('accessPanel');
    if (panel) panel.classList.toggle('open');
}

// Close panel when clicking outside
document.addEventListener('click', function(e) {
    const panel = document.getElementById('accessPanel');
    const fab = document.getElementById('accessFab');
    if (panel && fab && !panel.contains(e.target) && !fab.contains(e.target)) {
        panel.classList.remove('open');
    }
});

function resetAccess() {
    applyTheme('light');
    applyFontSize('normal');
    applyContrast(false);
    applyNoAnim(false);
    updateAccessButtons();
}

function updateAccessButtons() {
    const theme = document.documentElement.getAttribute('data-theme') || 'light';
    const fs = document.documentElement.getAttribute('data-fontsize') || 'normal';
    const contrast = document.documentElement.getAttribute('data-contrast') === 'on';
    const noanim = document.documentElement.getAttribute('data-noanim') === 'on';

    setActive('btn-theme-light', theme === 'light');
    setActive('btn-theme-dark', theme === 'dark');
    setActive('btn-fs-normal', fs === 'normal');
    setActive('btn-fs-lg', fs === 'lg');
    setActive('btn-fs-xl', fs === 'xl');
    setActive('btn-contrast', contrast);
    setActive('btn-noanim', noanim);
}

function setActive(id, active) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('active', active);
}
