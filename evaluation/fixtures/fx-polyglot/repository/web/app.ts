export interface HealthStatus {
  service: string;
  healthy: boolean;
}

export async function loadHealth(): Promise<HealthStatus> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return response.json() as Promise<HealthStatus>;
}
