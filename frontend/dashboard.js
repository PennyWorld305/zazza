class DashboardManager {
    constructor() {
        this.apiUrl = 'http://localhost:8000/api';
        this.currentTheme = 'light';
        this.currentSection = 'dashboard';
        
        this.initializeAuth();
        this.initializeEventListeners();
        this.loadUserInfo();
        this.loadTheme();
    }

    initializeAuth() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.href = 'login.html';
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
            window.location.href = 'login.html';
        }
    }

    initializeEventListeners() {
        // Navigation links - только для внутренних секций (с data-section)
        const navLinks = document.querySelectorAll('.nav-link[data-section]');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.getAttribute('data-section');
                this.switchSection(section);
            });
        });

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
    }

    switchSection(sectionName) {
        // Hide all sections
        const sections = document.querySelectorAll('.content-section');
        sections.forEach(section => {
            section.classList.add('hidden');
        });

        // Show selected section
        const targetSection = document.getElementById(`${sectionName}-section`);
        if (targetSection) {
            targetSection.classList.remove('hidden');
        }

        // Update navigation
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.classList.remove('active');
        });

        const activeLink = document.querySelector(`[data-section="${sectionName}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }

        // Update page title
        this.updatePageTitle(sectionName);
        this.currentSection = sectionName;
    }

    updatePageTitle(sectionName) {
        const titles = {
            'dashboard': 'Главная',
            'bots': 'Телеграмм боты',
            'employees': 'Сотрудники',
            'active-tickets': 'Активные тикеты',
            'archive-tickets': 'Архив тикетов',
            'chat': 'Чат сотрудников',
            'notes': 'Заметки'
        };

        const pageTitle = document.getElementById('page-title');
        if (pageTitle && titles[sectionName]) {
            pageTitle.textContent = titles[sectionName];
        }
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme();
        this.saveTheme();
    }

    applyTheme() {
        const body = document.body;
        const themeIcon = document.getElementById('theme-icon');
        
        if (this.currentTheme === 'dark') {
            body.classList.add('dark-theme');
            if (themeIcon) themeIcon.textContent = '☀️';
        } else {
            body.classList.remove('dark-theme');
            if (themeIcon) themeIcon.textContent = '🌙';
        }
    }

    saveTheme() {
        localStorage.setItem('theme', this.currentTheme);
    }

    loadTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            this.currentTheme = savedTheme;
            this.applyTheme();
        }
    }

    async loadUserInfo() {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        try {
            const response = await fetch(`${this.apiUrl}/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const userData = await response.json();
                this.currentUser = userData;
                this.updateUserDisplay();
            }
        } catch (error) {
            console.error('Error loading user info:', error);
        }
    }

    updateUserDisplay() {
        const usernameDisplay = document.getElementById('username-display');
        if (usernameDisplay && this.currentUser) {
            usernameDisplay.textContent = this.currentUser.username;
        }
    }

    showProfile() {
        window.location.href = '/static/profile.html';
    }

    logout() {
        if (confirm('Вы уверены, что хотите выйти?')) {
            localStorage.removeItem('access_token');
            window.location.href = 'login.html';
        }
    }

    // Utility method to make authenticated API calls
    async makeAuthenticatedRequest(url, options = {}) {
        const token = localStorage.getItem('access_token');
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, mergedOptions);
            
            if (response.status === 401) {
                // Token expired or invalid
                localStorage.removeItem('access_token');
                window.location.href = 'login.html';
                return null;
            }

            return response;
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }
}

// Add dark theme CSS variables
const darkThemeStyles = `
    body.dark-theme {
        --white: #1f2937;
        --light-gray: #374151;
        --border-gray: #4b5563;
        --text-gray: #d1d5db;
    }
    
    body.dark-theme .card {
        background-color: #374151;
        color: #f9fafb;
    }
    
    body.dark-theme .form-input {
        background-color: #4b5563;
        color: #f9fafb;
        border-color: #6b7280;
    }
    
    body.dark-theme .header {
        background-color: #374151;
        color: #f9fafb;
    }
    
    body.dark-theme .main-content {
        background-color: #1f2937;
    }
`;

// Inject dark theme styles
const styleSheet = document.createElement('style');
styleSheet.textContent = darkThemeStyles;
document.head.appendChild(styleSheet);

// Bots Management
class BotsManager {
    constructor(dashboardManager) {
        this.dashboardManager = dashboardManager;
        this.currentBotId = null;
        this.bots = [];
        
        this.loadBots();
    }

    async loadBots() {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${this.dashboardManager.apiUrl}/bots`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to load bots');
            }

            this.bots = await response.json();
            this.renderBotsTable();
        } catch (error) {
            console.error('Error loading bots:', error);
            this.showError('Ошибка загрузки ботов');
        }
    }

    renderBotsTable() {
        const tbody = document.getElementById('botsTableBody');
        
        if (this.bots.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="loading-row">Нет данных</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.bots.map(bot => `
            <tr>
                <td>${bot.id}</td>
                <td>${bot.name}</td>
                <td>${bot.telegram_name}</td>
                <td>${bot.token.substring(0, 20)}...</td>
                <td>${new Date(bot.created_at).toLocaleDateString('ru-RU')}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-edit" onclick="editBot(${bot.id})">
                            Редактировать
                        </button>
                        <button class="btn btn-delete" onclick="deleteBot(${bot.id}, '${bot.name}')">
                            Удалить
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    async saveBot(botData) {
        try {
            const token = localStorage.getItem('access_token');
            const url = this.currentBotId 
                ? `${this.dashboardManager.apiUrl}/bots/${this.currentBotId}`
                : `${this.dashboardManager.apiUrl}/bots`;
            
            const method = this.currentBotId ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(botData)
            });

            if (!response.ok) {
                throw new Error('Failed to save bot');
            }

            await this.loadBots();
            this.closeBotModal();
            this.showSuccess(this.currentBotId ? 'Бот обновлен' : 'Бот добавлен');
        } catch (error) {
            console.error('Error saving bot:', error);
            this.showError('Ошибка сохранения бота');
        }
    }

    async deleteBot(botId) {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${this.dashboardManager.apiUrl}/bots/${botId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to delete bot');
            }

            await this.loadBots();
            this.showSuccess('Бот удален');
        } catch (error) {
            console.error('Error deleting bot:', error);
            this.showError('Ошибка удаления бота');
        }
    }

    openBotModal(bot = null) {
        this.currentBotId = bot ? bot.id : null;
        const modal = document.getElementById('botModal');
        const title = document.getElementById('botModalTitle');
        const form = document.getElementById('botForm');

        title.textContent = bot ? 'Редактировать бота' : 'Добавить бота';
        
        if (bot) {
            document.getElementById('botName').value = bot.name;
            document.getElementById('botTelegramName').value = bot.telegram_name;
            document.getElementById('botToken').value = bot.token;
        } else {
            form.reset();
        }

        modal.style.display = 'block';
    }

    closeBotModal() {
        const modal = document.getElementById('botModal');
        modal.style.display = 'none';
        this.currentBotId = null;
    }

    openDeleteModal(botId, botName) {
        this.deleteBotId = botId;
        document.getElementById('deleteBotName').textContent = botName;
        document.getElementById('deleteModal').style.display = 'block';
    }

    closeDeleteModal() {
        document.getElementById('deleteModal').style.display = 'none';
        this.deleteBotId = null;
    }

    async confirmDeleteBot() {
        if (this.deleteBotId) {
            await this.deleteBot(this.deleteBotId);
            this.closeDeleteModal();
        }
    }

    showSuccess(message) {
        // Simple alert for now - can be enhanced with toast notifications
        alert('✓ ' + message);
    }

    showError(message) {
        alert('✗ ' + message);
    }
}

// Global functions for onclick handlers
let botsManager;

function openBotModal() {
    botsManager.openBotModal();
}

function closeBotModal() {
    botsManager.closeBotModal();
}

function editBot(botId) {
    const bot = botsManager.bots.find(b => b.id === botId);
    if (bot) {
        botsManager.openBotModal(bot);
    }
}

function deleteBot(botId, botName) {
    botsManager.openDeleteModal(botId, botName);
}

function closeDeleteModal() {
    botsManager.closeDeleteModal();
}

function confirmDeleteBot() {
    botsManager.confirmDeleteBot();
}

function saveBotData() {
    const form = document.getElementById('botForm');
    const formData = new FormData(form);
    
    const botData = {
        name: formData.get('name'),
        telegram_name: formData.get('telegram_name'),
        token: formData.get('token')
    };

    botsManager.saveBot(botData);
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const dashboardManager = new DashboardManager();
    
    // Initialize bots manager when switching to bots section
    dashboardManager.originalSwitchSection = dashboardManager.switchSection;
    dashboardManager.switchSection = function(sectionName) {
        this.originalSwitchSection(sectionName);
        
        if (sectionName === 'bots' && !botsManager) {
            botsManager = new BotsManager(this);
        }
    };
});