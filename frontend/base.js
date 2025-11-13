// Base Dashboard Manager - общие функции для всех страниц
class BaseDashboardManager {
    constructor() {
    this.apiUrl = 'http://91.229.8.214:8000/api';
        this.currentTheme = 'light';
        
        // Ждем загрузки DOM для полной инициализации
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
    }

    initialize() {
        this.initializeAuth();
        this.initializeEventListeners();
        this.loadUserInfo();
        this.loadTheme();
    }

    initializeAuth() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/static/login.html';
            return;
        }
        
        // Verify token
        this.verifyToken(token);
    }

    async verifyToken(token) {
        try {
            const response = await fetch(`${this.apiUrl}/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Token verification failed');
            }

            const userData = await response.json();
            this.currentUser = userData;
            this.updateUserDisplay();
        } catch (error) {
            console.error('Token verification error:', error);
            localStorage.removeItem('access_token');
            window.location.href = '/static/login.html';
        }
    }

    initializeEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }

        // Profile button
        const profileBtn = document.getElementById('profileBtn');
        if (profileBtn) {
            profileBtn.addEventListener('click', () => this.showProfile());
        }

        // Menu toggle for mobile
        const menuToggle = document.querySelector('.menu-toggle');
        if (menuToggle) {
            menuToggle.addEventListener('click', () => this.toggleSidebar());
        }

        // Navigation links
        this.initializeNavigation();

        // Close modals when clicking outside
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                e.target.style.display = 'none';
            }
        });
    }

    initializeNavigation() {
        // Добавляем обработчики для всех навигационных ссылок
        const navLinks = document.querySelectorAll('.nav-link[data-section]');
        navLinks.forEach(link => {
            // Устанавливаем правильный href для поддержки средней кнопки мыши и контекстного меню
            const section = link.getAttribute('data-section');
            const url = this.getSectionUrl(section);
            if (url) {
                link.href = url;
            }

            // Обработчик для обычного клика (левая кнопка мыши)
            link.addEventListener('click', (e) => {
                // Если пользователь держит Ctrl/Cmd или нажал среднюю кнопку, не мешаем браузеру
                if (e.ctrlKey || e.metaKey || e.which === 2) {
                    return; // Позволяем браузеру открыть в новой вкладке
                }
                
                // Обычная навигация
                e.preventDefault();
                this.navigateToSection(section);
            });

            // Обработчик для средней кнопки мыши (открытие в новой вкладке)
            link.addEventListener('mousedown', (e) => {
                if (e.which === 2) { // Средняя кнопка мыши
                    e.preventDefault();
                    window.open(url, '_blank');
                }
            });
        });
    }

    getSectionUrl(section) {
        // Определяем URL для каждого раздела
        const sectionUrls = {
            'dashboard': '/static/dashboard.html',
            'tgbot': '/static/tgbot.html',
            'employees': '/static/employees.html',
            'clients': '/static/clients.html',
            'tickets': '/static/tickets.html',
            'archive': '/static/archive.html',
            'chat': '/static/chat.html',
            'notes': '/static/notes.html'
        };

        return sectionUrls[section];
    }

    navigateToSection(section) {
        const url = this.getSectionUrl(section);
        if (url) {
            window.location.href = url;
        }
    }

    updateUserDisplay() {
        const usernameEl = document.getElementById('username');
        if (usernameEl && this.currentUser) {
            usernameEl.textContent = this.currentUser.display_name || this.currentUser.username;
        }
        
        // Управление навигацией на основе роли
        this.updateNavigationForRole();
    }

    updateNavigationForRole() {
        if (!this.currentUser || !this.currentUser.role) return;

        const role = this.currentUser.role;
        
        // Для курьера показываем только определенные разделы
        if (role === 'courier') {
            const allowedSections = ['tickets', 'archive', 'chat', 'notes'];
            this.hideNavigationSections(allowedSections, false); // false = скрываем клиенты
        }
        // Для оператора скрываем главную и телеграмм боты
        else if (role === 'operator') {
            const allowedSections = ['employees', 'clients', 'tickets', 'archive', 'chat', 'notes'];
            this.hideNavigationSections(allowedSections, true); // true = показываем клиенты
        }
    }

    hideNavigationSections(allowedSections, showClients) {
        const navItems = document.querySelectorAll('.nav-item');
        
        navItems.forEach(item => {
            const link = item.querySelector('.nav-link');
            if (link) {
                const section = link.getAttribute('data-section');
                
                if (section) {
                    // Скрываем все разделы, кроме разрешенных
                    if (!allowedSections.includes(section)) {
                        item.style.display = 'none';
                    } else {
                        item.style.display = 'block';
                    }
                    
                    // Специальная обработка для клиентов
                    if (section === 'clients') {
                        item.style.display = showClients ? 'block' : 'none';
                    }
                }
            }
        });
        
        // Если мы на недопустимой странице, перенаправляем на разрешенный раздел
        const currentSection = document.querySelector('.nav-link.active')?.getAttribute('data-section');
        if (currentSection && !allowedSections.includes(currentSection)) {
            // Переключаем на активные тикеты
            const ticketsLink = document.getElementById('nav-tickets');
            if (ticketsLink) {
                ticketsLink.click();
            }
        }
    }

    loadUserInfo() {
        // Load user info from localStorage or make API call
        const username = localStorage.getItem('username');
        if (username) {
            const usernameEl = document.getElementById('username');
            if (usernameEl) {
                usernameEl.textContent = username;
            }
        }
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.body.classList.toggle('dark-theme');
        localStorage.setItem('theme', this.currentTheme);
        
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.textContent = this.currentTheme === 'light' ? '🌙' : '☀️';
        }
    }

    loadTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            this.currentTheme = savedTheme;
            if (savedTheme === 'dark') {
                document.body.classList.add('dark-theme');
                const themeToggle = document.getElementById('themeToggle');
                if (themeToggle) {
                    themeToggle.textContent = '☀️';
                }
            }
        }
    }

    toggleSidebar() {
        document.body.classList.toggle('sidebar-collapsed');
    }

    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        localStorage.removeItem('theme');
        window.location.href = '/static/login.html';
    }

    showProfile() {
        window.location.href = '/static/profile.html';
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type = 'info') {
        // Simple notification system
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'} ${message}</span>
            <button onclick="this.parentElement.remove()">&times;</button>
        `;
        
        // Add notification styles if not exist
        if (!document.getElementById('notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                .notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    border-radius: 6px;
                    color: white;
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    min-width: 250px;
                    animation: slideInRight 0.3s ease;
                }
                .notification-success { background-color: #10b981; }
                .notification-error { background-color: #ef4444; }
                .notification-info { background-color: #3b82f6; }
                .notification button {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 18px;
                    cursor: pointer;
                    margin-left: auto;
                }
                @keyframes slideInRight {
                    from { transform: translateX(100%); }
                    to { transform: translateX(0); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }
}

// Dark theme styles
const darkThemeStyles = `
    body.dark-theme {
        background-color: #1f2937;
        color: #f9fafb;
    }
    
    body.dark-theme .sidebar {
        background-color: #374151;
    }
    
    body.dark-theme .card {
        background-color: #374151;
        border-color: #4b5563;
    }
    
    body.dark-theme .header {
        background-color: #374151;
        color: #f9fafb;
    }
    
    body.dark-theme .main-content {
        background-color: #1f2937;
    }

    body.dark-theme .modal-content {
        background-color: #374151;
        color: #f9fafb;
    }

    body.dark-theme .form-group input,
    body.dark-theme .form-group textarea,
    body.dark-theme .form-group select {
        background-color: #4b5563;
        color: #f9fafb;
        border-color: #6b7280;
    }

    body.dark-theme .data-table {
        background-color: #374151;
    }

    body.dark-theme .data-table tbody tr:hover {
        background-color: #4b5563;
    }
`;

// Inject dark theme styles
const styleSheet = document.createElement('style');
styleSheet.textContent = darkThemeStyles;
document.head.appendChild(styleSheet);

// Utility functions for compatibility
function getToken() {
    return localStorage.getItem('access_token');
}

function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.href = '/static/login.html';
        return false;
    }
    return true;
}

function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/static/login.html';
}

// Initialize base dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (!window.baseDashboard) {
        window.baseDashboard = new BaseDashboardManager();
    }
});