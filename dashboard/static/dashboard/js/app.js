const sidebar = document.getElementById('sidebar');
const backdrop = document.getElementById('sidebar-backdrop');
const toggle = document.getElementById('menu-toggle');

function setMenu(open) {
  sidebar.classList.toggle('open', open);
  backdrop.classList.toggle('visible', open);
  document.body.style.overflow = open ? 'hidden' : '';
}

toggle.addEventListener('click', () => setMenu(!sidebar.classList.contains('open')));
backdrop.addEventListener('click', () => setMenu(false));
window.addEventListener('resize', () => {
  if (window.innerWidth > 760) setMenu(false);
});
