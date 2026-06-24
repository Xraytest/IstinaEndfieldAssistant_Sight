function showToast(message, type = 'info', title = '') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        container.id = 'toastContainer';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const iconMap = {
        success: '\u2713',
        error: '\u2715',
        warning: '\u26a0',
        info: '\u2139'
    };

    const typeColors = {
        success: 'var(--success)',
        error: 'var(--error)',
        warning: 'var(--warning)',
        info: 'var(--info)'
    };

    toast.innerHTML = `
        <div class="toast-icon" style="color: ${typeColors[type] || typeColors.info}">${iconMap[type] || iconMap.info}</div>
        <div class="toast-content">
            ${title ? `<div class="toast-title">${title}</div>` : ''}
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">\u00d7</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function initThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    if (!themeToggle) return;

    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });
}

function initMobileNav() {
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const navOverlay = document.getElementById('navOverlay');
    if (!mobileMenuToggle || !navOverlay) return;

    mobileMenuToggle.addEventListener('click', () => {
        const mainNav = document.getElementById('mainNav');
        if (!mainNav) return;
        mainNav.classList.toggle('mobile-open');
        navOverlay.classList.toggle('active');
        const isOpen = mainNav.classList.contains('mobile-open');
        mobileMenuToggle.setAttribute('aria-expanded', isOpen);
    });
}

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
            if (e.key === 'Escape') {
                const mainNav = document.getElementById('mainNav');
                const navOverlay = document.getElementById('navOverlay');
                if (mainNav) mainNav.classList.remove('mobile-open');
                if (navOverlay) navOverlay.classList.remove('active');
            }
            return;
        }

        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'L') {
            e.preventDefault();
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }

        if (e.key === 'Escape') {
            const mainNav = document.getElementById('mainNav');
            const navOverlay = document.getElementById('navOverlay');
            if (mainNav) mainNav.classList.remove('mobile-open');
            if (navOverlay) navOverlay.classList.remove('active');
            document.querySelectorAll('.nav-dropdown').forEach(d => {
                const toggle = d.querySelector('.nav-dropdown-toggle');
                if (toggle) toggle.setAttribute('aria-expanded', 'false');
                d.setAttribute('data-open', 'false');
            });
            const userMenuContainer = document.querySelector('.user-menu-container');
            if (userMenuContainer) userMenuContainer.setAttribute('data-open', 'false');
        }
    });
}

function initWsStatusIndicator() {
    const wsStatusDot = document.getElementById('wsStatusDot');
    const wsStatusText = document.getElementById('wsStatusText');
    if (!wsStatusDot || !wsStatusText) return;

    wsStatusDot.style.background = 'var(--text-muted)';
    wsStatusText.textContent = '\u7981\u7ebf';

    fetch('/api/server/info')
        .then(r => r.json())
        .then(() => {
            wsStatusDot.style.background = 'var(--success)';
            wsStatusDot.style.boxShadow = '0 0 8px var(--success)';
            wsStatusText.textContent = '\u5728\u7ebf';
        })
        .catch(() => {
            wsStatusDot.style.background = 'var(--error)';
            wsStatusText.textContent = '\u7981\u7ebf';
        });
}

function loadUserInfo() {
    const userNameEl = document.querySelector('.user-name');
    const userEmailEl = document.querySelector('.user-email');

    if (!userNameEl && !userEmailEl) return;

    fetch('/api/server/info')
        .then(r => r.json())
        .then(data => {
            if (userNameEl) {
                userNameEl.textContent = data.admin_name || data.server_name || '\u7ba1\u7406\u5458';
            }
            if (userEmailEl) {
                userEmailEl.textContent = data.admin_email || data.contact || '';
            }
        })
        .catch(() => {
            if (userNameEl) userNameEl.textContent = '\u7ba1\u7406\u5458';
            if (userEmailEl) userEmailEl.textContent = '';
        });
}

function initSharedFeatures() {
    initThemeToggle();
    initMobileNav();
    initKeyboardShortcuts();
    initWsStatusIndicator();
    loadUserInfo();
}

document.addEventListener('DOMContentLoaded', initSharedFeatures);

window.showToast = showToast;
window.initSharedFeatures = initSharedFeatures;
window.initThemeToggle = initThemeToggle;
window.loadUserInfo = loadUserInfo;