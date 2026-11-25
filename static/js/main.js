// Student Task Manager - Main JavaScript Application File

document.addEventListener('DOMContentLoaded', function () {
    // 1. Sidebar Toggle for Mobile
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const appSidebar = document.getElementById('appSidebar');

    if (sidebarToggleBtn && appSidebar) {
        sidebarToggleBtn.addEventListener('click', function () {
            appSidebar.classList.toggle('show');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function (e) {
            if (window.innerWidth < 992) {
                if (!appSidebar.contains(e.target) && !sidebarToggleBtn.contains(e.target) && appSidebar.classList.contains('show')) {
                    appSidebar.classList.remove('show');
                }
            }
        });
    }

    // 2. CSRF Token extraction for fetch requests
    function getCsrfToken() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        return metaTag ? metaTag.getAttribute('content') : '';
    }

    // 3. Instant Task Status Quick-Toggle (AJAX)
    const toggleButtons = document.querySelectorAll('.task-toggle-btn');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const taskId = this.getAttribute('data-task-id');
            const card = document.getElementById(`task-card-${taskId}`);
            const checkIcon = this.querySelector('i');

            fetch(`/tasks/${taskId}/toggle`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (data.is_completed) {
                        this.classList.add('completed');
                        if (card) card.classList.add('task-completed');
                    } else {
                        this.classList.remove('completed');
                        if (card) card.classList.remove('task-completed');
                    }
                    // Update badge if available
                    const badge = document.getElementById(`task-status-badge-${taskId}`);
                    if (badge) {
                        badge.textContent = data.status;
                        badge.className = `badge-pill-custom ${data.status_badge_class}`;
                    }
                }
            })
            .catch(err => console.error('Error toggling task:', err));
        });
    });

    // 4. Quick Notification Read (AJAX)
    const markReadButtons = document.querySelectorAll('.mark-notif-read-btn');
    markReadButtons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const notifId = this.getAttribute('data-notif-id');
            const notifCard = document.getElementById(`notif-card-${notifId}`);

            fetch(`/notifications/${notifId}/read`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success && notifCard) {
                    notifCard.classList.remove('unread');
                    this.remove();
                }
            })
            .catch(err => console.error('Error marking notification read:', err));
        });
    });

    // 5. Auto dismiss flash alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });
});
