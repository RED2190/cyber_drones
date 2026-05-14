# coverage_controller.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class CoverageController:
    def __init__(self, mock: bool = True):
        self.mock = mock
    
    async def get_coverage(self, repo_url: str, commit_hash: str) -> Optional[float]:
        if self.mock:
            # Возвращаем высокое покрытие для доверенных
            logger.info(f"Mock coverage for {repo_url}: 85%")
            return 85.0
        # Здесь реальный запрос к CI системе
        # ...
        return None