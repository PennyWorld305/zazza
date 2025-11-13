// Bots Management - функционал для страницы tgbot.html
class BotsManager {
    constructor() {
    this.apiUrl = '/api';
        this.currentBotId = null;
        this.bots = [];
        this.deleteBotId = null;
        
        this.loadBots();
    }

    async loadBots() {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${this.apiUrl}/bots`, {
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
                    <td colspan="7" class="loading-row">Нет данных</td>
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
                <td>
                    <span class="status-badge ${bot.is_active ? 'status-active' : 'status-inactive'}">
                        ${bot.is_active ? '✅ Активен' : '⏸️ Пауза'}
                    </span>
                </td>
                <td>${new Date(bot.created_at).toLocaleDateString('ru-RU')}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-edit" onclick="editBot(${bot.id})">
                            Редактировать
                        </button>
                        <button class="btn btn-status ${bot.is_active ? 'btn-pause' : 'btn-activate'}" onclick="toggleBotStatus(${bot.id})">
                            ${bot.is_active ? '⏸️ Пауза' : '▶️ Активировать'}
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
                ? `${this.apiUrl}/bots/${this.currentBotId}`
                : `${this.apiUrl}/bots`;
            
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
                const errorData = await response.text();
                console.error('Server error:', errorData);
                throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
            }

            await this.loadBots();
            this.closeBotModal();
            this.showSuccess(this.currentBotId ? 'Бот обновлен' : 'Бот добавлен');
        } catch (error) {
            console.error('Error saving bot:', error);
            this.showError('Ошибка сохранения бота: ' + error.message);
        }
    }

    async deleteBot(botId) {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${this.apiUrl}/bots/${botId}`, {
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

    async toggleBotStatus(botId) {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${this.apiUrl}/bots/${botId}/status`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to toggle bot status');
            }

            await this.loadBots();
            this.showSuccess('Статус бота изменен');
        } catch (error) {
            console.error('Error toggling bot status:', error);
            this.showError('Ошибка изменения статуса бота');
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
        // Use the base dashboard notification system
        if (window.baseDashboard) {
            window.baseDashboard.showSuccess(message);
        } else {
            alert('✓ ' + message);
        }
    }

    showError(message) {
        if (window.baseDashboard) {
            window.baseDashboard.showError(message);
        } else {
            alert('✗ ' + message);
        }
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

function toggleBotStatus(botId) {
    botsManager.toggleBotStatus(botId);
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
    
    // Validate form
    if (!formData.get('name') || !formData.get('telegram_name') || !formData.get('token')) {
        botsManager.showError('Пожалуйста, заполните все поля');
        return;
    }
    
    const botData = {
        name: formData.get('name'),
        telegram_name: formData.get('telegram_name'),
        token: formData.get('token')
    };

    botsManager.saveBot(botData);
}

// Initialize bots manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Wait for base dashboard to be initialized
    const initBotsManager = () => {
        if (window.baseDashboard) {
            botsManager = new BotsManager();
        } else {
            // Retry after a short delay
            setTimeout(initBotsManager, 50);
        }
    };
    
    initBotsManager();
});