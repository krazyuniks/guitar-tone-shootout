"""Domain-to-Remotion props serialisation.

Converts GTS domain entities (CompositionSpec) to Remotion-compatible JSON props.
"""

from typing import Any

from core.domain.value_objects.composition_spec import CompositionSpec


def serialize_composition_props(spec: CompositionSpec) -> dict[str, Any]:
    """Serialize CompositionSpec to Remotion props.

    Args:
        spec: Domain composition specification

    Returns:
        Remotion-compatible JSON props dictionary

    The returned dictionary contains:
    - compositionType: str - type of composition
    - data: dict - composition-specific data
    """
    return {
        "compositionType": spec.composition_type,
        "data": spec.data,
    }


def validate_remotion_props(props: dict[str, Any]) -> bool:
    """Validate Remotion props structure.

    Args:
        props: Remotion props dictionary to validate

    Returns:
        True if props has required structure, False otherwise
    """
    if not isinstance(props, dict):
        return False

    if "compositionType" not in props:
        return False

    if "data" not in props:
        return False

    if not isinstance(props["data"], dict):
        return False

    return True


def deserialize_composition_props(props: dict[str, Any]) -> CompositionSpec:
    """Deserialize Remotion props to CompositionSpec.

    Args:
        props: Remotion props dictionary

    Returns:
        Domain composition specification

    Raises:
        ValueError: If props structure is invalid
    """
    if not validate_remotion_props(props):
        raise ValueError("Invalid Remotion props structure")

    return CompositionSpec(
        composition_type=props["compositionType"],
        data=props["data"],
    )


# British English aliases
serialise_composition_props = serialize_composition_props
deserialise_composition_props = deserialize_composition_props
