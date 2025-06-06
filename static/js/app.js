
// Общие функции для приложения

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.querySelector('main').prepend(alertDiv);
    
    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Форматирование чисел
function formatCurrency(amount) {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB'
    }).format(amount);
}

// Форматирование дат
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('ru-RU');
}
