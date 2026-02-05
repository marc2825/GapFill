function setLang(lang) {
    const body = document.body;
    const btns = document.querySelectorAll('.lang-btn');
    
    // Toggle body class
    if (lang === 'jp') {
        body.classList.add('lang-jp');
        body.classList.remove('lang-en');
    } else {
        body.classList.add('lang-en');
        body.classList.remove('lang-jp');
    }

    btns.forEach(btn => {
        if (btn.textContent.toLowerCase() === lang) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const blocks = Array.from(document.querySelectorAll('.content-block'));
    if (blocks.length === 0) return;

    const revealTargets = blocks.slice(1);
    revealTargets.forEach(block => block.classList.add('reveal'));
    const revealParts = Array.from(document.querySelectorAll('.reveal-part'));
    revealParts.forEach(part => part.classList.add('reveal-part'));

    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15 }
    );

    revealTargets.forEach(block => observer.observe(block));
    revealParts.forEach(part => observer.observe(part));
});
