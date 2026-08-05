from __future__ import annotations

from collections import defaultdict

from .contracts import Capability, CapabilityDescriptor, CapabilityRef


class CapabilityRegistryError(RuntimeError):
    pass


class CapabilityAlreadyRegisteredError(CapabilityRegistryError):
    pass


class CapabilityNotFoundError(CapabilityRegistryError):
    pass


def semver_key(version: str) -> tuple[int, int, int, int, str]:
    core, separator, prerelease = version.partition("-")
    major, minor, patch = (int(item) for item in core.split("."))
    stable_rank = 1 if not separator else 0
    return major, minor, patch, stable_rank, prerelease


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Capability]] = defaultdict(dict)

    def register(self, capability: Capability) -> CapabilityRef:
        descriptor = capability.descriptor
        versions = self._capabilities[descriptor.name]
        if descriptor.version in versions:
            raise CapabilityAlreadyRegisteredError(descriptor.ref.canonical_name)
        versions[descriptor.version] = capability
        return descriptor.ref

    def resolve(self, name: str, version: str | None = None) -> Capability:
        versions = self._capabilities.get(name)
        if not versions:
            raise CapabilityNotFoundError(name)
        if version is None:
            stable_versions = [item for item in versions if "-" not in item]
            selected = max(stable_versions or versions, key=semver_key)
        else:
            selected = version
        try:
            return versions[selected]
        except KeyError as exc:
            raise CapabilityNotFoundError(f"{name}@{selected}") from exc

    def descriptor(self, name: str, version: str | None = None) -> CapabilityDescriptor:
        return self.resolve(name, version).descriptor

    def contains(self, ref: CapabilityRef) -> bool:
        return ref.name in self._capabilities and ref.version in self._capabilities[ref.name]

    def list_descriptors(self, name: str | None = None) -> tuple[CapabilityDescriptor, ...]:
        capabilities = (
            self._capabilities.get(name, {}).values()
            if name is not None
            else (
                capability
                for versions in self._capabilities.values()
                for capability in versions.values()
            )
        )
        return tuple(
            sorted(
                (capability.descriptor for capability in capabilities),
                key=lambda item: (item.name, semver_key(item.version)),
            )
        )
