"""
CAD block definitions for architectural symbols.
Defines standard blocks for doors, windows, fixtures, etc.
"""

from typing import List, Tuple
import ezdxf
from ezdxf.layouts import BlockLayout


def create_door_block(block_layout: BlockLayout, width: float = 1.0) -> None:
    """
    Create a door symbol block (simplified door swing).

    Args:
        block_layout: ezdxf block layout to add to
        width: Door opening width in DXF units
    """
    # Door opening (arc for swing)
    block_layout.add_arc(
        center=(0, 0),
        radius=width / 2,
        start_angle=0,
        end_angle=90,
        dxfattribs={"layer": "SYMBOLS"},
    )
    # Door frame (rectangle)
    block_layout.add_lwpolyline(
        points=[(-width / 2, 0), (width / 2, 0), (width / 2, 0.1), (-width / 2, 0.1)],
        dxfattribs={"layer": "SYMBOLS"},
    )


def create_window_block(block_layout: BlockLayout, width: float = 1.0) -> None:
    """
    Create a window symbol block (simple rectangle with cross).

    Args:
        block_layout: ezdxf block layout to add to
        width: Window width in DXF units
    """
    # Window frame (double line)
    half_w = width / 2
    block_layout.add_lwpolyline(
        points=[(-half_w, -0.1), (half_w, -0.1), (half_w, 0.1), (-half_w, 0.1)],
        dxfattribs={"layer": "SYMBOLS"},
    )
    # Cross pattern (interior)
    block_layout.add_line((-half_w, 0), (half_w, 0), dxfattribs={"layer": "SYMBOLS"})


def create_staircase_block(block_layout: BlockLayout) -> None:
    """
    Create a staircase symbol block (diagonal lines).

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Staircase represented as diagonal lines
    for i in range(5):
        y = i * 0.2
        block_layout.add_line(
            (0, y), (0.2 + y * 0.1, y + 0.2),
            dxfattribs={"layer": "SYMBOLS"},
        )
    # Arrow showing direction
    block_layout.add_lwpolyline(
        points=[(0.8, 1.0), (1.0, 1.2), (0.8, 1.0), (0.6, 1.2)],
        dxfattribs={"layer": "SYMBOLS"},
    )


def create_fixture_block(block_layout: BlockLayout) -> None:
    """
    Create a generic fixture symbol block (circle with cross).

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Circle for fixture
    block_layout.add_circle((0, 0), radius=0.3, dxfattribs={"layer": "SYMBOLS"})
    # Cross inside
    block_layout.add_line(
        (-0.3, 0), (0.3, 0), dxfattribs={"layer": "SYMBOLS"}
    )
    block_layout.add_line(
        (0, -0.3), (0, 0.3), dxfattribs={"layer": "SYMBOLS"}
    )


def create_wall_hatch(block_layout: BlockLayout) -> None:
    """
    Create a hatched wall pattern (cross-hatch for wall fill).

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Diagonal lines for wall pattern
    for i in range(-2, 3):
        block_layout.add_line(
            (i * 0.2, -1), (i * 0.2 + 2, 1),
            dxfattribs={"layer": "WALLS"},
        )


def setup_standard_blocks(dwg) -> None:
    """
    Set up all standard architectural blocks in a DXF document.

    Args:
        dwg: ezdxf DXFDocument to add blocks to
    """
    blocks = dwg.blocks

    # Create DOOR block if it doesn't exist
    if "DOOR" not in blocks:
        door_block = blocks.new(name="DOOR")
        create_door_block(door_block, width=1.0)

    # Create WINDOW block if it doesn't exist
    if "WINDOW" not in blocks:
        window_block = blocks.new(name="WINDOW")
        create_window_block(window_block, width=1.0)

    # Create STAIRCASE block if it doesn't exist
    if "STAIRCASE" not in blocks:
        staircase_block = blocks.new(name="STAIRCASE")
        create_staircase_block(staircase_block)

    # Create FIXTURE block if it doesn't exist
    if "FIXTURE" not in blocks:
        fixture_block = blocks.new(name="FIXTURE")
        create_fixture_block(fixture_block)

    # Create WALL_HATCH block if it doesn't exist
    if "WALL_HATCH" not in blocks:
        wall_hatch = blocks.new(name="WALL_HATCH")
        create_wall_hatch(wall_hatch)


def get_block_name_for_symbol(symbol_type: str) -> str:
    """
    Get the block name for a given symbol type.

    Args:
        symbol_type: Symbol type string (e.g., "door", "window")

    Returns:
        Block name to use
    """
    mapping = {
        "door": "DOOR",
        "window": "WINDOW",
        "staircase": "STAIRCASE",
        "stairs": "STAIRCASE",
        "fixture": "FIXTURE",
        "toilet": "FIXTURE",
        "sink": "FIXTURE",
        "bathtub": "FIXTURE",
    }
    return mapping.get(symbol_type.lower(), "FIXTURE")
