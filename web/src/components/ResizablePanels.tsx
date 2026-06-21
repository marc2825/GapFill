import { useEffect } from 'react';

export const useResizablePanels = () => {
  useEffect(() => {
    let isResizing = false;
    let currentPanel: HTMLElement | null = null;
    let startX = 0;
    let startWidth = 0;

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('resize-handle')) {
        isResizing = true;
        currentPanel = target.closest('.resizable-panel') as HTMLElement;
        startX = e.clientX;
        startWidth = currentPanel ? currentPanel.offsetWidth : 0;
        document.body.classList.add('resizing');
        e.preventDefault();
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !currentPanel) return;

      const resizeHandle = currentPanel.querySelector('.resize-handle') as HTMLElement;
      
      if (resizeHandle.classList.contains('resize-handle-right')) {
        // Left panel resizing
        const deltaX = e.clientX - startX;
        const newWidth = Math.max(200, Math.min(600, startWidth + deltaX));
        currentPanel.style.width = `${newWidth}px`;
      } else if (resizeHandle.classList.contains('resize-handle-left')) {
        // Right panel resizing
        const deltaX = startX - e.clientX;
        const newWidth = Math.max(200, Math.min(600, startWidth + deltaX));
        currentPanel.style.width = `${newWidth}px`;
      }
    };

    const handleMouseUp = () => {
      isResizing = false;
      currentPanel = null;
      document.body.classList.remove('resizing');
    };

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);
};
