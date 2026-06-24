/**
 * ═════════════════════════════════════════════════════════════════════════════
 * IstinaPlatform Dashboard v2.0 - 导航和交互脚本
 * 处理: 导航菜单、下拉菜单、主题切换、编辑模式、响应式交互
 * ═════════════════════════════════════════════════════════════════════════════
 */

// ═════════════════════════════════════════════════════════════════════════════
// 1. 初始化和全局配置
// ═════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initializeNavigation();
  initializeThemeToggle();
  initializeUserMenu();
  initializeDropdowns();
  initializeKeyboardShortcuts();
  initializeCharts();
  initializeResponsive();
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. 导航菜单交互
// ═════════════════════════════════════════════════════════════════════════════

function initializeNavigation() {
  const mobileMenuToggle = document.getElementById('mobileMenuToggle');
  const mainNav = document.getElementById('mainNav');
  const navOverlay = document.getElementById('navOverlay');

  if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', () => {
      toggleMobileNav();
    });
  }

  if (navOverlay) {
    navOverlay.addEventListener('click', closeMobileNav);
  }

  // 导航链接点击处理
  const navLinks = document.querySelectorAll('.nav-link:not(.nav-dropdown-toggle)');
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      // 关闭移动菜单
      closeMobileNav();
      
      // 更新活跃链接
      navLinks.forEach(l => l.classList.remove('nav-link-active'));
      link.classList.add('nav-link-active');
    });
  });

  // 点击导航外的其他地方时关闭菜单
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.app-nav') && !e.target.closest('.mobile-menu-toggle')) {
      closeMobileNav();
    }
  });
}

function toggleMobileNav() {
  const mainNav = document.getElementById('mainNav');
  const navOverlay = document.getElementById('navOverlay');
  const mobileMenuToggle = document.getElementById('mobileMenuToggle');

  mainNav.classList.toggle('mobile-open');
  navOverlay.classList.toggle('active');
  
  const isOpen = mainNav.classList.contains('mobile-open');
  mobileMenuToggle.setAttribute('aria-expanded', isOpen);
}

function closeMobileNav() {
  const mainNav = document.getElementById('mainNav');
  const navOverlay = document.getElementById('navOverlay');
  const mobileMenuToggle = document.getElementById('mobileMenuToggle');

  mainNav.classList.remove('mobile-open');
  navOverlay.classList.remove('active');
  mobileMenuToggle.setAttribute('aria-expanded', 'false');
}

// ═════════════════════════════════════════════════════════════════════════════
// 3. 下拉菜单交互
// ═════════════════════════════════════════════════════════════════════════════

function initializeDropdowns() {
  const dropdowns = document.querySelectorAll('.nav-dropdown');

  dropdowns.forEach(dropdown => {
    const toggle = dropdown.querySelector('.nav-dropdown-toggle');
    const menu = dropdown.querySelector('.nav-dropdown-menu');

    if (!toggle || !menu) return;

    // 点击切换按钮
    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
      
      // 关闭其他下拉菜单
      dropdowns.forEach(d => {
        if (d !== dropdown) {
          d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
          d.setAttribute('data-open', 'false');
        }
      });

      // 切换当前下拉菜单
      toggle.setAttribute('aria-expanded', !isExpanded);
      dropdown.setAttribute('data-open', !isExpanded);
    });

    // 点击菜单项
    const items = menu.querySelectorAll('.dropdown-item');
    items.forEach(item => {
      item.addEventListener('click', () => {
        toggle.setAttribute('aria-expanded', 'false');
        dropdown.setAttribute('data-open', 'false');
      });
    });
  });

  // 点击外部关闭下拉菜单
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-dropdown')) {
      dropdowns.forEach(d => {
        d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
        d.setAttribute('data-open', 'false');
      });
    }
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// 4. 主题切换
// ═════════════════════════════════════════════════════════════════════════════

function initializeThemeToggle() {
  const themeToggle = document.getElementById('themeToggle');
  const html = document.documentElement;

  // 从 localStorage 读取主题偏好
  const savedTheme = localStorage.getItem('theme');
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const initialTheme = savedTheme || systemTheme;

  html.setAttribute('data-theme', initialTheme);

  // 主题切换按钮
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }

  // 监听系统主题变化
  window.matchMedia('(prefers-color-scheme: dark)').addListener((e) => {
    if (!localStorage.getItem('theme')) {
      html.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    }
  });
}

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

  html.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
}

// ═════════════════════════════════════════════════════════════════════════════
// 5. 用户菜单
// ═════════════════════════════════════════════════════════════════════════════

function initializeUserMenu() {
  const userMenuContainer = document.querySelector('.user-menu-container');
  const userMenuTrigger = document.querySelector('.user-menu-trigger');

  if (!userMenuContainer || !userMenuTrigger) return;

  userMenuTrigger.addEventListener('click', (e) => {
    e.preventDefault();
    const isOpen = userMenuContainer.getAttribute('data-open') === 'true';
    userMenuContainer.setAttribute('data-open', !isOpen);
    userMenuTrigger.setAttribute('aria-expanded', !isOpen);
  });

  // 点击外部关闭
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.user-menu-container')) {
      userMenuContainer.setAttribute('data-open', 'false');
      userMenuTrigger.setAttribute('aria-expanded', 'false');
    }
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// 6. 键盘快捷键
// ═════════════════════════════════════════════════════════════════════════════

function initializeKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K: 打开搜索
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('.search-input');
      if (searchInput) {
        searchInput.focus();
      }
    }

    // Ctrl/Cmd + Shift + L: 切换主题
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'L') {
      e.preventDefault();
      toggleTheme();
    }

    // Escape: 关闭菜单和下拉框
    if (e.key === 'Escape') {
      closeMobileNav();
      document.querySelectorAll('.nav-dropdown').forEach(d => {
        d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
        d.setAttribute('data-open', 'false');
      });

      const userMenuContainer = document.querySelector('.user-menu-container');
      if (userMenuContainer) {
        userMenuContainer.setAttribute('data-open', 'false');
      }
    }
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// 7. 仪表板功能
// ═════════════════════════════════════════════════════════════════════════════

function toggleEditMode() {
  console.log('编辑模式切换 - 功能开发中');
  // TODO: 实现小部件编辑模式
}

function showWidgetLibrary() {
  console.log('小部件库打开 - 功能开发中');
  // TODO: 实现小部件库模态框
}

function loadPreset(presetName) {
  console.log('加载预设布局:', presetName);
  // TODO: 实现不同预设的加载逻辑
}

function refreshDashboard() {
  // 刷新数据
  console.log('刷新仪表板数据');
  
  // 显示加载状态
  const buttons = document.querySelectorAll('[onclick="refreshDashboard()"]');
  buttons.forEach(btn => {
    btn.disabled = true;
    const svg = btn.querySelector('svg');
    if (svg) {
      svg.style.animation = 'spin 1s linear infinite';
    }
  });

  // 模拟数据刷新延迟
  setTimeout(() => {
    buttons.forEach(btn => {
      btn.disabled = false;
      const svg = btn.querySelector('svg');
      if (svg) {
        svg.style.animation = '';
      }
    });
  }, 1000);
}

// ═════════════════════════════════════════════════════════════════════════════
// 8. 图表初始化
// ═════════════════════════════════════════════════════════════════════════════

function initializeCharts() {
  // 用户增长图表
  const userGrowthCtx = document.getElementById('userGrowthChart');
  if (userGrowthCtx) {
    new Chart(userGrowthCtx, {
      type: 'line',
      data: {
        labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
        datasets: [{
          label: '用户数',
          data: [120, 135, 128, 145, 160, 175, 190],
          borderColor: 'var(--accent-primary)',
          backgroundColor: 'rgba(0, 212, 255, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: 'var(--accent-primary)',
          pointBorderColor: 'var(--bg-primary)',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            display: true,
            labels: {
              color: 'var(--text-secondary)',
              font: { size: 12 }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: 'var(--text-secondary)' },
            grid: { color: 'var(--border-primary)' }
          },
          x: {
            ticks: { color: 'var(--text-secondary)' },
            grid: { color: 'var(--border-primary)' }
          }
        }
      }
    });
  }

  // 任务状态分布图表
  const taskStatusCtx = document.getElementById('taskStatusChart');
  if (taskStatusCtx) {
    new Chart(taskStatusCtx, {
      type: 'doughnut',
      data: {
        labels: ['已完成', '进行中', '待开始', '已延期'],
        datasets: [{
          data: [120, 85, 35, 5],
          backgroundColor: [
            'var(--success)',
            'var(--warning)',
            'var(--info)',
            'var(--error)'
          ],
          borderColor: 'var(--bg-card)',
          borderWidth: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: 'var(--text-secondary)',
              font: { size: 12 },
              padding: 20
            }
          }
        }
      }
    });
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// 9. WebSocket 连接状态
// ═════════════════════════════════════════════════════════════════════════════

function updateWebSocketStatus(isConnected) {
  const dot = document.getElementById('wsStatusDot');
  const text = document.getElementById('wsStatusText');

  if (dot && text) {
    if (isConnected) {
      dot.classList.add('online');
      text.textContent = '在线';
    } else {
      dot.classList.remove('online');
      text.textContent = '离线';
    }
  }
}

// 初始化 WebSocket（如果需要）
function initializeWebSocket() {
  // TODO: 实现实时连接
  // const ws = new WebSocket('ws://your-server');
  // ws.onopen = () => updateWebSocketStatus(true);
  // ws.onclose = () => updateWebSocketStatus(false);
}

// ═════════════════════════════════════════════════════════════════════════════
// 10. 响应式功能
// ═════════════════════════════════════════════════════════════════════════════

function initializeResponsive() {
  const mediaQuery = window.matchMedia('(max-width: 768px)');

  // 处理视口变化
  mediaQuery.addListener((e) => {
    if (e.matches) {
      // 进入移动视图
      closeMobileNav();
    }
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// 11. 搜索功能
// ═════════════════════════════════════════════════════════════════════════════

function initializeSearch() {
  const searchInput = document.querySelector('.search-input');

  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    console.log('搜索:', query);
    // TODO: 实现搜索逻辑
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const query = e.target.value;
      console.log('执行搜索:', query);
      // TODO: 执行搜索
    }
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// 12. 数据过滤
// ═════════════════════════════════════════════════════════════════════════════

function initializeFilters() {
  const filters = document.querySelectorAll('.filter-select');

  filters.forEach(filter => {
    filter.addEventListener('change', (e) => {
      const filterType = e.target.id;
      const value = e.target.value;
      console.log(`筛选 ${filterType}: ${value}`);
      // TODO: 实现过滤逻辑
    });
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// 13. 工具函数
// ═════════════════════════════════════════════════════════════════════════════

/**
 * 格式化数字为可读格式 (例: 1000 -> 1k)
 */
function formatNumber(num) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k';
  }
  return num.toString();
}

/**
 * 格式化时间
 */
function formatTime(date) {
  return new Date(date).toLocaleString('zh-CN');
}

/**
 * 防抖函数
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * 节流函数
 */
function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// ═════════════════════════════════════════════════════════════════════════════
// 14. 导出功能
// ═════════════════════════════════════════════════════════════════════════════

function exportData(format = 'json') {
  console.log('导出数据格式:', format);
  // TODO: 实现数据导出
}

function exportChart(chartId, format = 'png') {
  console.log('导出图表:', chartId, format);
  // TODO: 实现图表导出
}

// ═════════════════════════════════════════════════════════════════════════════
// 15. 通知系统
// ═════════════════════════════════════════════════════════════════════════════

function showNotification(message, type = 'info', duration = 3000) {
  const notification = document.createElement('div');
  notification.className = `toast toast-${type}`;
  notification.textContent = message;

  document.body.appendChild(notification);

  // 显示动画
  setTimeout(() => notification.classList.add('show'), 10);

  // 自动移除
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => notification.remove(), 300);
  }, duration);
}

// ═════════════════════════════════════════════════════════════════════════════
// 16. 辅助函数初始化
// ═════════════════════════════════════════════════════════════════════════════

// 初始化所有功能（已在 DOMContentLoaded 中调用）
// 如果需要，可以手动调用以下函数：
// initializeSearch();
// initializeFilters();
// initializeWebSocket();

// ═════════════════════════════════════════════════════════════════════════════
// 17. 控制台调试信息
// ═════════════════════════════════════════════════════════════════════════════

console.log('%c🚀 IstinaPlatform Dashboard v2.0', 'color: #00d4ff; font-size: 16px; font-weight: bold;');
console.log('%c✅ 前端交互系统已加载', 'color: #10b981; font-size: 12px;');
console.log('%c📌 快捷键: Ctrl+K (搜索), Ctrl+Shift+L (主题), Esc (关闭菜单)', 'color: #f59e0b; font-size: 11px;');
