/**
 * Detect if an error is due to an order no longer being OPEN.
 * Used when an operation fails after the order was paid/cancelled on another terminal.
 */
export function isOrderNotOpenError(errorMessage: string): boolean {
  return errorMessage.toLowerCase().includes("only an open order");
}
