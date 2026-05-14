"""
Orchestrator — компонент оркестрации дронопорта.
Координирует работу PortManager, PowerHealthManager, DroneRegistry через StateStore.
"""

__version__ = "1.0.0"

# Экспорт публичных классов для удобных импортов
from .orchestrator import Orchestrator

__all__ = [
    "Orchestrator",
]
