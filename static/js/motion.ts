/* Motion/animation utilities - TypeScript */
function fadeIn(element: HTMLElement, duration: number = 300): void {
  element.style.opacity = '0';
  element.style.transition = `opacity ${duration}ms ease`;
  requestAnimationFrame(() => {
    element.style.opacity = '1';
  });
}

function fadeOut(element: HTMLElement, duration: number = 300): Promise<void> {
  return new Promise((resolve) => {
    element.style.transition = `opacity ${duration}ms ease`;
    element.style.opacity = '0';
    setTimeout(() => {
      element.style.display = 'none';
      resolve();
    }, duration);
  });
}

function slideDown(element: HTMLElement, duration: number = 300): void {
  element.style.height = '0';
  element.style.overflow = 'hidden';
  element.style.transition = `height ${duration}ms ease`;
  const height = element.scrollHeight;
  requestAnimationFrame(() => {
    element.style.height = height + 'px';
  });
}

(window as any).fadeIn = fadeIn;
(window as any).fadeOut = fadeOut;
(window as any).slideDown = slideDown;