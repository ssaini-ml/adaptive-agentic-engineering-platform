from dataclasses import dataclass


@dataclass
class HealthStatus:
    service: str = "python-api"
    healthy: bool = True


def health() -> HealthStatus:
    return HealthStatus()
