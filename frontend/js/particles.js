// Floating particles animation
(function initParticles() {
  const c = document.getElementById('particles-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');

  function resize() {
    c.width  = window.innerWidth;
    c.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const particles = Array.from({ length: 60 }, () => ({
    x:     Math.random() * c.width,
    y:     Math.random() * c.height,
    r:     Math.random() * 1.5 + 0.3,
    dx:    (Math.random() - 0.5) * 0.3,
    dy:    (Math.random() - 0.5) * 0.3,
    o:     Math.random() * 0.4 + 0.1,
    color: Math.random() > 0.5 ? '0,212,255' : '124,58,237'
  }));

  function draw() {
    ctx.clearRect(0, 0, c.width, c.height);
    particles.forEach(p => {
      p.x += p.dx;
      p.y += p.dy;
      if (p.x < 0 || p.x > c.width)  p.dx *= -1;
      if (p.y < 0 || p.y > c.height) p.dy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.color},${p.o})`;
      ctx.fill();
    });
    requestAnimationFrame(draw);
  }
  draw();
}());
