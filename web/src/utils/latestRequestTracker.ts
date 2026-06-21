export class LatestRequestTracker {
  private currentRequestId = 0;

  begin(): number {
    this.currentRequestId++;
    return this.currentRequestId;
  }

  isCurrent(requestId: number): boolean {
    return this.currentRequestId === requestId;
  }
}

export function isCurrentGenerationRequest(
  tracker: LatestRequestTracker,
  requestId: number,
  requestGeneration: number,
  currentGeneration: number,
): boolean {
  return (
    requestGeneration === currentGeneration &&
    tracker.isCurrent(requestId)
  );
}
