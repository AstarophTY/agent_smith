from typing import Iterable, Set


class AllowedAttributeBases:
    """Builds an allowlist of attribute base names for call validation."""

    @staticmethod
    def build(authorized_imports: Iterable[str]) -> Set[str]:
        """Build an allowlist of attribute base names.

        Args:
            authorized_imports (Iterable[str]): Import patterns to extract base
                names from.

        Returns:
            Set[str]: Base module names allowed for attribute calls.
        """
        bases: Set[str] = set()
        for pattern in authorized_imports:
            base = pattern.split(".")[0]
            if base:
                bases.add(base)
        return bases
