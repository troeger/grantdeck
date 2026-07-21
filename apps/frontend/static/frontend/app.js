document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-copy-target]');
  if (!button) return;

  const source = document.getElementById(button.dataset.copyTarget);
  if (!source) return;

  navigator.clipboard.writeText(source.textContent.trim());
});
