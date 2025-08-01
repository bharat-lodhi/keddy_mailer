// script.js
document.addEventListener('DOMContentLoaded', function() {
    // Chart.js Configuration
    const ctx = document.getElementById('revenueChart').getContext('2d');
    
    const chartData = {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        datasets: [{
            label: 'Revenue',
            data: [65000, 75000, 55000, 85000, 95000, 105000, 125000, 115000, 135000, 145000, 155000, 165000],
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#3b82f6',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 6,
            pointHoverRadius: 8
        }]
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                backgroundColor: '#1f2937',
                titleColor: '#ffffff',
                bodyColor: '#ffffff',
                cornerRadius: 8,
                displayColors: false
            }
        },
        scales: {
            x: {
                border: {
                    display: false
                },
                grid: {
                    display: false
                },
                ticks: {
                    color: '#6b7280'
                }
            },
            y: {
                border: {
                    display: false
                },
                grid: {
                    color: '#f3f4f6'
                },
                ticks: {
                    color: '#6b7280',
                    callback: function(value) {
                        return '$' + (value / 1000) + 'k';
                    }
                }
            }
        },
        interaction: {
            intersect: false,
            mode: 'index'
        }
    };

    const revenueChart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: chartOptions
    });

    // Chart Toggle Functionality
    const toggleButtons = document.querySelectorAll('.toggle-btn');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons
            toggleButtons.forEach(btn => btn.classList.remove('active'));
            // Add active class to clicked button
            this.classList.add('active');
            
            // Change chart type
            const chartType = this.getAttribute('data-chart');
            revenueChart.config.type = chartType;
            revenueChart.update();
        });
    });

    // Navigation Active State
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            // Remove active class from all nav items
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
            // Add active class to parent of clicked link
            this.closest('.nav-item').classList.add('active');
        });
    });

    // Search Functionality
    const searchInput = document.querySelector('.search-input');
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const navItems = document.querySelectorAll('.nav-item');
        
        navItems.forEach(item => {
            const linkText = item.querySelector('.nav-link').textContent.toLowerCase();
            if (linkText.includes(searchTerm)) {
                item.style.display = 'block';
            } else {
                item.style.display = searchTerm === '' ? 'block' : 'none';
            }
        });
    });

    // Animate counters on page load
    function animateCounter(element, target) {
        let current = 0;
        const increment = target / 100;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            element.textContent = Math.floor(current).toLocaleString();
        }, 20);
    }

    // Animate summary card values
    const cardValues = document.querySelectorAll('.card-value');
    cardValues.forEach(card => {
        const target = parseInt(card.textContent.replace(/,/g, ''));
        animateCounter(card, target);
    });
});
