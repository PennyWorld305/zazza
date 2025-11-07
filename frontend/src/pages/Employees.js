import React, { useState, useEffect } from 'react';
import './Employees.css';

const Employees = () => {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [formData, setFormData] = useState({
    login: '',
    name: '',
    password: '',
    role: 'operator'
  });

  useEffect(() => {
    fetchEmployees();
  }, []);

  const fetchEmployees = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:8000/api/employees', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setEmployees(data.employees);
      } else {
        console.error('Ошибка при получении сотрудников');
      }
    } catch (error) {
      console.error('Ошибка:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('token');
      const url = editingEmployee 
        ? `http://localhost:8000/api/employees/${editingEmployee.id}`
        : 'http://localhost:8000/api/employees';
      
      const method = editingEmployee ? 'PUT' : 'POST';
      
      const body = editingEmployee 
        ? { name: formData.name, role: formData.role, is_active: true }
        : formData;

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(body)
      });

      if (response.ok) {
        await fetchEmployees();
        setShowModal(false);
        setEditingEmployee(null);
        setFormData({ login: '', name: '', password: '', role: 'operator' });
      } else {
        const errorData = await response.json();
        alert(errorData.detail || 'Ошибка при сохранении сотрудника');
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка при сохранении сотрудника');
    }
  };

  const handleEdit = (employee) => {
    setEditingEmployee(employee);
    setFormData({
      login: employee.login,
      name: employee.name,
      password: '',
      role: employee.role
    });
    setShowModal(true);
  };

  const handleDelete = async (employeeId) => {
    if (!window.confirm('Вы уверены, что хотите удалить этого сотрудника?')) {
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/employees/${employeeId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        await fetchEmployees();
      } else {
        const errorData = await response.json();
        alert(errorData.detail || 'Ошибка при удалении сотрудника');
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка при удалении сотрудника');
    }
  };

  const toggleEmployeeStatus = async (employee) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/employees/${employee.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: employee.name,
          role: employee.role,
          is_active: !employee.is_active
        })
      });

      if (response.ok) {
        await fetchEmployees();
      } else {
        const errorData = await response.json();
        alert(errorData.detail || 'Ошибка при изменении статуса');
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка при изменении статуса');
    }
  };

  const getRoleText = (role) => {
    switch (role) {
      case 'admin': return 'Администратор';
      case 'operator': return 'Оператор';
      case 'courier': return 'Курьер';
      default: return role;
    }
  };

  const openAddModal = () => {
    setEditingEmployee(null);
    setFormData({ login: '', name: '', password: '', role: 'operator' });
    setShowModal(true);
  };

  if (loading) {
    return <div className="employees-loading">Загрузка...</div>;
  }

  return (
    <div className="employees">
      <div className="employees-header">
        <h2>Управление сотрудниками</h2>
        <button className="btn btn-primary" onClick={openAddModal}>
          <span className="btn-icon">+</span>
          Добавить сотрудника
        </button>
      </div>

      <div className="employees-table">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Логин</th>
              <th>Имя</th>
              <th>Роль</th>
              <th>Статус</th>
              <th>Создан</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {employees.map(employee => (
              <tr key={employee.id}>
                <td>{employee.id}</td>
                <td>{employee.login}</td>
                <td>{employee.name}</td>
                <td>
                  <span className={`role-badge role-${employee.role}`}>
                    {getRoleText(employee.role)}
                  </span>
                </td>
                <td>
                  <button 
                    className={`status-btn ${employee.is_active ? 'active' : 'inactive'}`}
                    onClick={() => toggleEmployeeStatus(employee)}
                  >
                    {employee.is_active ? 'Активен' : 'Неактивен'}
                  </button>
                </td>
                <td>
                  {employee.created_at 
                    ? new Date(employee.created_at).toLocaleDateString('ru-RU')
                    : '-'
                  }
                </td>
                <td className="table-actions">
                  <button 
                    className="btn btn-sm btn-secondary"
                    onClick={() => handleEdit(employee)}
                  >
                    Редактировать
                  </button>
                  {employee.role !== 'admin' && (
                    <button 
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDelete(employee.id)}
                    >
                      Удалить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {editingEmployee ? 'Редактировать сотрудника' : 'Добавить сотрудника'}
              </h3>
              <button 
                className="modal-close"
                onClick={() => setShowModal(false)}
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="modal-body">
              {!editingEmployee && (
                <div className="form-group">
                  <label>Логин:</label>
                  <input
                    type="text"
                    value={formData.login}
                    onChange={(e) => setFormData({...formData, login: e.target.value})}
                    required
                  />
                </div>
              )}
              
              <div className="form-group">
                <label>Имя:</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                />
              </div>
              
              {!editingEmployee && (
                <div className="form-group">
                  <label>Пароль:</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required
                  />
                </div>
              )}
              
              <div className="form-group">
                <label>Роль:</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                  required
                >
                  <option value="operator">Оператор</option>
                  <option value="courier">Курьер</option>
                  <option value="admin">Администратор</option>
                </select>
              </div>
              
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Отмена
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingEmployee ? 'Сохранить' : 'Создать'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Employees;