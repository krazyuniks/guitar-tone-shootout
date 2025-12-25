"""Configuration loading and validation for comparison INI files."""

import configparser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ComparisonMeta:
    """Metadata about the comparison."""

    name: str
    author: str
    description: str = ""


@dataclass
class DITrack:
    """A DI track with its metadata."""

    file: Path
    guitar: str
    pickup: str
    notes: str = ""


@dataclass
class ChainEffect:
    """A single effect in a signal chain."""

    effect_type: str  # nam, ir, eq, reverb, delay, gain, vst
    value: str  # path or preset name


@dataclass
class SignalChain:
    """A complete signal chain (ordered sequence of effects)."""

    name: str
    description: str
    chain: list[ChainEffect]


@dataclass
class Comparison:
    """A complete comparison configuration."""

    meta: ComparisonMeta
    di_tracks: list[DITrack]
    signal_chains: list[SignalChain]
    source_path: Path = field(default_factory=Path)

    @property
    def segment_count(self) -> int:
        """Total number of segments to generate (DI tracks x signal chains)."""
        return len(self.di_tracks) * len(self.signal_chains)

    def get_segments(self) -> list[tuple[DITrack, SignalChain]]:
        """
        Generate all segments in order.

        Returns list of (di_track, signal_chain) tuples.
        Order: signal_chains outer loop, di_tracks inner loop.
        """
        segments: list[tuple[DITrack, SignalChain]] = []
        for signal_chain in self.signal_chains:
            for di_track in self.di_tracks:
                segments.append((di_track, signal_chain))
        return segments


def load_comparison(ini_path: Path) -> Comparison:
    """
    Load and validate a comparison INI file.

    Args:
        ini_path: Path to the INI file

    Returns:
        Validated Comparison object

    Raises:
        ValueError: If required sections or keys are missing
        FileNotFoundError: If referenced files don't exist
    """
    config = configparser.ConfigParser()
    config.read(ini_path)

    # Validate required sections
    required_sections = ["meta", "di_tracks", "signal_chains"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section: [{section}]")

    # Load metadata
    meta_section = config["meta"]
    meta = ComparisonMeta(
        name=meta_section.get("name", "Untitled Comparison"),
        author=meta_section.get("author", "Anonymous"),
        description=meta_section.get("description", ""),
    )

    # Load DI tracks
    di_tracks = _load_di_tracks(config["di_tracks"])

    # Load signal chains
    signal_chains = _load_signal_chains(config["signal_chains"])

    # Validate we have at least one of each
    if not di_tracks:
        raise ValueError("At least one DI track is required")
    if not signal_chains:
        raise ValueError("At least one signal chain is required")

    return Comparison(
        meta=meta,
        di_tracks=di_tracks,
        signal_chains=signal_chains,
        source_path=ini_path,
    )


def _load_di_tracks(section: configparser.SectionProxy) -> list[DITrack]:
    """
    Load DI tracks from an INI section.

    Format: N.field = value (e.g., 1.file = track.wav, 1.guitar = Strat)

    Args:
        section: ConfigParser section with numbered DI track entries

    Returns:
        List of DITrack objects in order
    """
    # Group entries by their number prefix
    tracks_data: dict[int, dict[str, str]] = {}

    for key, value in section.items():
        if "." not in key:
            continue

        num_str, field_name = key.split(".", 1)
        if not num_str.isdigit():
            continue

        num = int(num_str)
        if num not in tracks_data:
            tracks_data[num] = {}
        tracks_data[num][field_name] = value

    # Convert to DITrack objects
    di_tracks: list[DITrack] = []
    base_path = Path("inputs/di_tracks")

    for num in sorted(tracks_data.keys()):
        data = tracks_data[num]

        if "file" not in data:
            raise ValueError(f"DI track {num} missing required 'file' field")

        file_path = base_path / data["file"]

        di_tracks.append(
            DITrack(
                file=file_path,
                guitar=data.get("guitar", "Unknown"),
                pickup=data.get("pickup", "Unknown"),
                notes=data.get("notes", ""),
            )
        )

    return di_tracks


def _load_signal_chains(section: configparser.SectionProxy) -> list[SignalChain]:
    """
    Load signal chains from an INI section.

    Format: N.field = value (e.g., 1.name = Plexi Crunch, 1.chain = nam:..., ir:...)

    Args:
        section: ConfigParser section with numbered signal chain entries

    Returns:
        List of SignalChain objects in order
    """
    # Group entries by their number prefix
    chains_data: dict[int, dict[str, str]] = {}

    for key, value in section.items():
        if "." not in key:
            continue

        num_str, field_name = key.split(".", 1)
        if not num_str.isdigit():
            continue

        num = int(num_str)
        if num not in chains_data:
            chains_data[num] = {}
        chains_data[num][field_name] = value

    # Convert to SignalChain objects
    signal_chains: list[SignalChain] = []

    for num in sorted(chains_data.keys()):
        data = chains_data[num]

        if "name" not in data:
            raise ValueError(f"Signal chain {num} missing required 'name' field")
        if "chain" not in data:
            raise ValueError(f"Signal chain {num} missing required 'chain' field")

        # Parse chain effects
        chain_effects = _parse_chain(data["chain"])

        signal_chains.append(
            SignalChain(
                name=data["name"],
                description=data.get("description", ""),
                chain=chain_effects,
            )
        )

    return signal_chains


def _parse_chain(chain_str: str) -> list[ChainEffect]:
    """
    Parse a chain string into ChainEffect objects.

    Format: "type:value, type:value, ..."
    Example: "eq:highpass_80hz, nam:plexi.nam, ir:greenback.wav"

    Args:
        chain_str: Comma-separated chain definition

    Returns:
        List of ChainEffect objects in order
    """
    effects: list[ChainEffect] = []

    for raw_part in chain_str.split(","):
        part = raw_part.strip()
        if not part:
            continue

        if ":" not in part:
            raise ValueError(f"Invalid chain effect format: '{part}' (expected 'type:value')")

        effect_type, value = part.split(":", 1)
        effect_type = effect_type.strip().lower()
        value = value.strip()

        # Validate effect type
        valid_types = {"nam", "ir", "eq", "reverb", "delay", "gain", "vst"}
        if effect_type not in valid_types:
            raise ValueError(f"Unknown effect type: '{effect_type}' (valid: {valid_types})")

        effects.append(ChainEffect(effect_type=effect_type, value=value))

    return effects
