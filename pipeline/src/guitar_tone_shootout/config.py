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
    value: str  # path or preset name (or alias for nam_sources)


@dataclass
class NAMSource:
    """
    NAM model source for auto-download from Tone3000.

    Defines where to fetch a NAM model if not present locally.
    """

    alias: str  # Key used in signal chain (e.g., "jcm800")
    url: str  # Tone3000 page URL
    model: str  # Specific capture/model name to download

    @property
    def local_dir(self) -> Path:
        """Directory where downloaded model should be stored."""
        # Extract slug from URL (e.g., "jcm800-44269" from ".../tones/jcm800-44269")
        slug = self.url.rstrip("/").split("/")[-1]
        return Path("inputs/nam_models/tone3000") / slug


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
    nam_sources: dict[str, NAMSource] = field(default_factory=dict)
    source_path: Path = field(default_factory=Path)
    project_root: Path = field(default_factory=Path)

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

    # Resolve project root (INI files are in comparisons/, so go up one level)
    project_root = ini_path.parent.parent.resolve()

    # Load DI tracks
    di_tracks = _load_di_tracks(config["di_tracks"], project_root)

    # Load signal chains
    signal_chains = _load_signal_chains(config["signal_chains"])

    # Load NAM sources (optional section)
    nam_sources: dict[str, NAMSource] = {}
    if "nam_sources" in config:
        nam_sources = _load_nam_sources(config["nam_sources"])

    # Validate we have at least one of each
    if not di_tracks:
        raise ValueError("At least one DI track is required")
    if not signal_chains:
        raise ValueError("At least one signal chain is required")

    return Comparison(
        meta=meta,
        di_tracks=di_tracks,
        signal_chains=signal_chains,
        nam_sources=nam_sources,
        source_path=ini_path,
        project_root=project_root,
    )


def _load_di_tracks(section: configparser.SectionProxy, base_dir: Path) -> list[DITrack]:
    """
    Load DI tracks from an INI section.

    Format: N.field = value (e.g., 1.file = track.wav, 1.guitar = Strat)

    Args:
        section: ConfigParser section with numbered DI track entries
        base_dir: Base directory for resolving relative paths (INI file's parent)

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
    # Resolve inputs/di_tracks relative to the INI file's directory
    inputs_path = base_dir / "inputs" / "di_tracks"

    for num in sorted(tracks_data.keys()):
        data = tracks_data[num]

        if "file" not in data:
            raise ValueError(f"DI track {num} missing required 'file' field")

        file_path = inputs_path / data["file"]

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


def _load_nam_sources(section: configparser.SectionProxy) -> dict[str, NAMSource]:
    """
    Load NAM sources from an INI section.

    Format:
        alias.url = https://www.tone3000.com/tones/jcm800-44269
        alias.model = JCM800 capture 3

    Args:
        section: ConfigParser section with NAM source definitions

    Returns:
        Dict mapping alias to NAMSource objects
    """
    # Group entries by their alias prefix
    sources_data: dict[str, dict[str, str]] = {}

    for key, value in section.items():
        if "." not in key:
            continue

        alias, field_name = key.split(".", 1)
        alias = alias.strip()
        field_name = field_name.strip().lower()

        if alias not in sources_data:
            sources_data[alias] = {}
        sources_data[alias][field_name] = value

    # Convert to NAMSource objects
    nam_sources: dict[str, NAMSource] = {}

    for alias, data in sources_data.items():
        if "url" not in data:
            raise ValueError(f"NAM source '{alias}' missing required 'url' field")
        if "model" not in data:
            raise ValueError(f"NAM source '{alias}' missing required 'model' field")

        nam_sources[alias] = NAMSource(
            alias=alias,
            url=data["url"],
            model=data["model"],
        )

    return nam_sources
