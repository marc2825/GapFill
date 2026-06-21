export function logInDev(...args: unknown[]): void {
  if (import.meta.env.DEV) {
    console.log(...args);
  }
}

export function warnInDev(...args: unknown[]): void {
  if (import.meta.env.DEV) {
    console.warn(...args);
  }
}

export function errorInDev(...args: unknown[]): void {
  if (import.meta.env.DEV) {
    console.error(...args);
  }
}
