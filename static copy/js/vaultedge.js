// VaultEdge Custom JS

// Sticky navbar on scroll
window.addEventListener('scroll', function() {
    var header = document.getElementById('ve-sticky');
    if (header) {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    }
});

// Mobile menu toggle
var toggler = document.getElementById('ve-toggle');
var mobileMenu = document.getElementById('ve-mobile-menu');
if (toggler && mobileMenu) {
    toggler.addEventListener('click', function() {
        mobileMenu.classList.toggle('open');
    });
}

// Mobile Market submenu toggle
document.addEventListener('DOMContentLoaded', function() {
    var marketLink = document.querySelector('.ve-mobile-menu > ul > li:nth-child(4) > a');
    var marketSubmenu = document.querySelector('.ve-mobile-menu > ul > li:nth-child(4) > ul');
    
    if (marketLink && marketSubmenu) {
        marketLink.addEventListener('click', function(e) {
            e.preventDefault();
            if (marketSubmenu.style.display === 'none' || !marketSubmenu.style.display) {
                marketSubmenu.style.display = 'block';
                marketLink.style.color = 'var(--ve-gold)';
            } else {
                marketSubmenu.style.display = 'none';
                marketLink.style.color = '';
            }
        });
    }
});

// Counter animation
function animateCounters() {
    var counters = document.querySelectorAll('.counter');
    counters.forEach(function(counter) {
        var target = parseInt(counter.getAttribute('data-count'));
        var count = 0;
        var duration = 2000;
        var step = target / (duration / 16);
        var timer = setInterval(function() {
            count += step;
            if (count >= target) {
                counter.textContent = target.toLocaleString();
                clearInterval(timer);
            } else {
                counter.textContent = Math.floor(count).toLocaleString();
            }
        }, 16);
    });
}

// Trigger counters when in view
var counterSection = document.querySelector('.ve-counter-section');
if (counterSection) {
    var triggered = false;
    var observer = new IntersectionObserver(function(entries) {
        if (entries[0].isIntersecting && !triggered) {
            triggered = true;
            animateCounters();
        }
    }, { threshold: 0.3 });
    observer.observe(counterSection);
}

// FAQ accordion toggle
document.querySelectorAll('.ve-faq-q').forEach(function(q) {
    q.addEventListener('click', function() {
        var item = this.closest('.ve-faq-item');
        var wasOpen = item.classList.contains('open');
        document.querySelectorAll('.ve-faq-item').forEach(function(i) { i.classList.remove('open'); });
        if (!wasOpen) item.classList.add('open');
    });
});
