from typing import Iterable, Set


class AllowedAttributeBases:
    """Builds an allowlist of attribute base names for call validation."""

    @staticmethod
    def build(authorized_imports: Iterable[str]) -> Set[str]:
        bases: Set[str] = set()
        for pattern in authorized_imports:
            base = pattern.split(".")[0]
            if base:
                bases.add(base)
        return bases
