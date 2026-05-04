from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AnnotationObject:
    class_name: str
    class_id: int
    bbox: List[float] = field(default_factory=list)  # [x1, y1, x2, y2] absolute pixels
    confidence: Optional[float] = None


@dataclass
class Annotation:
    image_path: str
    width: int
    height: int
    objects: List[AnnotationObject] = field(default_factory=list)


class ClassMapping:
    def __init__(self):
        self._name_to_id: dict[str, int] = {}
        self._id_to_name: dict[int, str] = {}

    def add(self, name: str, class_id: int):
        self._name_to_id[name] = class_id
        self._id_to_name[class_id] = name

    def get_id(self, name: str) -> int:
        return self._name_to_id.get(name, -1)

    def get_name(self, class_id: int) -> str:
        return self._id_to_name.get(class_id, f"class_{class_id}")

    @property
    def names(self) -> list[str]:
        return list(self._name_to_id.keys())

    @property
    def ids(self) -> list[int]:
        return list(self._id_to_name.keys())

    def __len__(self):
        return len(self._name_to_id)

    @classmethod
    def from_names(cls, names: list[str]) -> "ClassMapping":
        mapping = cls()
        for i, name in enumerate(names):
            mapping.add(name, i)
        return mapping
