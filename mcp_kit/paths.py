"""Белый список каталогов, из которых сервер читает файлы.

Инструмент, принимающий путь (например `extract_stamps`), не должен
превращаться в «прочитай любой файл на диске» и тем более в «создай
каталог рядом с любым путём». Проверка — `realpath` (снимает `..`,
симлинки и junction'ы) плюс `commonpath` (проверяет принадлежность
корню).
"""
from __future__ import annotations

import os
from typing import Sequence

from .errors import ToolError


class RootPolicy:
    """Каталоги, из которых сервер вправе читать файлы."""

    def __init__(self, roots: Sequence[str | os.PathLike[str]]) -> None:
        if not roots:
            raise ValueError("нужен хотя бы один разрешённый корень")
        self.roots = [os.path.realpath(os.path.abspath(str(r)))
                      for r in roots]

    @staticmethod
    def _within(path: str, root: str) -> bool:
        try:
            return os.path.commonpath([path, root]) == root
        except ValueError:
            # разные диски в Windows — commonpath бросает исключение
            return False

    def resolve(self, path: str) -> str:
        """Абсолютный путь внутри корня; иначе `ToolError`."""
        raw = str(path or "").strip()
        if not raw:
            raise ToolError("путь не задан", code="path_not_allowed")
        target = os.path.realpath(os.path.abspath(raw))
        if not any(self._within(target, root) for root in self.roots):
            raise ToolError(
                f"путь вне разрешённых корней: {target}",
                code="path_not_allowed")
        return target

    def codec_dir_for(self, pdf_path: str, fallback_root: str) -> str:
        """Каталог кэша декодера шрифтов.

        Рядом с PDF — только если этот каталог сам внутри разрешённого
        корня. Иначе — во временном каталоге вызова: создавать
        каталоги на диске по произвольному пути нельзя.
        """
        candidate = os.path.splitext(pdf_path)[0] + ".codec"
        if any(self._within(os.path.realpath(candidate), root)
               for root in self.roots):
            return candidate
        return os.path.join(fallback_root, "codec")
