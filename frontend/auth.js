class AuthManager {
    constructor() {
        this.apiUrl = 'http://localhost:8000/api';
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Login form only
        const loginForm = document.getElementById('loginForm');

        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        // Принудительно скрываем загрузчик при инициализации
        this.setLoading('login', false);

        // Check if user is already logged in
        this.checkAuthStatus();
    }

    showAlert(message, type = 'error', containerId = 'alert-container') {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="alert alert-${type}">
                ${message}
            </div>
        `;

        // Auto hide after 5 seconds
        setTimeout(() => {
            container.innerHTML = '';
        }, 5000);
    }



    setLoading(formType, isLoading) {
        const btn = document.getElementById(`${formType}Btn`);
        const text = document.getElementById(`${formType}Text`);
        const loader = document.getElementById(`${formType}Loader`);

        console.log(`Изменение состояния загрузки ${formType}: ${isLoading}`);
        console.log('Элементы найдены:', { btn: !!btn, text: !!text, loader: !!loader });

        if (btn) {
            btn.disabled = isLoading;
        }

        if (text) {
            if (isLoading) {
                text.classList.add('hidden');
            } else {
                text.classList.remove('hidden');
            }
        }

        if (loader) {
            if (isLoading) {
                loader.classList.remove('hidden');
            } else {
                loader.classList.add('hidden');
            }
        }
    }

    validateForm(formData) {
        const errors = [];

        if (!formData.username || formData.username.length < 3) {
            errors.push('Имя пользователя должно содержать минимум 3 символа');
        }

        if (!formData.password || formData.password.length < 6) {
            errors.push('Пароль должен содержать минимум 6 символов');
        }

        return errors;
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    async handleLogin(event) {
        event.preventDefault();
        console.log('Начинаем авторизацию...');
        this.setLoading('login', true);

        const formData = new FormData(event.target);
        const loginData = {
            username: formData.get('username'),
            password: formData.get('password')
        };

        console.log('Данные для входа:', loginData);

        const validationErrors = this.validateForm(loginData);
        if (validationErrors.length > 0) {
            console.log('Ошибки валидации:', validationErrors);
            this.showAlert(validationErrors.join('<br>'));
            this.setLoading('login', false);
            return;
        }

        try {
            console.log('Отправляем запрос на:', `${this.apiUrl}/login`);
            const response = await fetch(`${this.apiUrl}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(loginData)
            });

            console.log('Статус ответа:', response.status);
            const data = await response.json();
            console.log('Данные ответа:', data);

            if (response.ok) {
                // Save token to localStorage
                localStorage.setItem('access_token', data.access_token);
                
                this.showAlert('Успешная авторизация! Перенаправление...', 'success');
                
                // Redirect to dashboard
                setTimeout(() => {
                    window.location.href = '/static/dashboard.html';
                }, 1000);
            } else {
                this.showAlert(data.detail || 'Ошибка авторизации');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showAlert('Ошибка соединения с сервером');
        } finally {
            this.setLoading('login', false);
        }
    }



    checkAuthStatus() {
        const token = localStorage.getItem('access_token');
        if (token) {
            // Verify token with server
            this.verifyToken(token);
        }
    }

    async verifyToken(token) {
        try {
            const response = await fetch(`${this.apiUrl}/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                // Token is valid, redirect to dashboard
                window.location.href = '/static/dashboard.html';
            } else {
                // Token is invalid, remove it
                localStorage.removeItem('access_token');
            }
        } catch (error) {
            console.error('Token verification error:', error);
            localStorage.removeItem('access_token');
        }
    }
}

// Initialize auth manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AuthManager();
});