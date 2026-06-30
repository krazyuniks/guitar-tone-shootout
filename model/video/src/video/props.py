"""Domain-to-Remotion props serialisation.

Converts GTS domain entities (CompositionSpec) to Remotion-compatible JSON props.
"""

from gts.domain.value_objects.composition_spec import CompositionSpec


def serialize_composition_props(spec: CompositionSpec) -> dict[str, object]:
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


def validate_remotion_props(props: dict[str, object]) -> bool:
    """Validate Remotion props structure.

    Args:
        props: Remotion props dictionary to validate

    Returns:
        True if props has required structure, False otherwise
    """
    if "compositionType" not in props:
        return False

    if "data" not in props:
        return False

    return isinstance(props["data"], dict)


def deserialize_composition_props(props: dict[str, object]) -> CompositionSpec:
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

    composition_type = props["compositionType"]
    data = props["data"]
    if not isinstance(composition_type, str):
        raise ValueError("compositionType must be a string")
    if not isinstance(data, dict):
        raise ValueError("data must be a dict")

    return CompositionSpec(
        composition_type=composition_type,
        data=data,
    )


# British English aliases
serialise_composition_props = serialize_composition_props
deserialise_composition_props = deserialize_composition_props
