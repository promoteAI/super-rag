type ToastType = 'success' | 'error' | 'info';

const TOAST_DURATION = 3000;

export function showToast(message: string, type: ToastType = 'success') {
  const existing = document.querySelector('.app-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `app-toast app-toast--${type}`;

  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span class="app-toast__icon">${icon}</span><span class="app-toast__msg">${message}</span>`;

  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('app-toast--visible'));

  setTimeout(() => {
    toast.classList.remove('app-toast--visible');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    setTimeout(() => toast.remove(), 400);
  }, TOAST_DURATION);
}
