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


def create_wc_block(block_layout: BlockLayout) -> None:
    """
    Create a WC (toilet) symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Toilet bowl (circle)
    block_layout.add_circle((0, 0), radius=0.3, dxfattribs={"layer": "SYMBOLS"})
    # Toilet seat (slightly larger ellipse outline)
    block_layout.add_lwpolyline(
        points=[(-0.35, -0.1), (-0.35, 0.35), (0.35, 0.35), (0.35, -0.1)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )


def create_shower_block(block_layout: BlockLayout) -> None:
    """
    Create a shower/bath symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Shower tray (rectangle)
    block_layout.add_lwpolyline(
        points=[(-0.4, -0.3), (0.4, -0.3), (0.4, 0.4), (-0.4, 0.4)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )
    # Shower head (small circle with water drops)
    block_layout.add_circle((0, 0.3), radius=0.1, dxfattribs={"layer": "SYMBOLS"})
    # Water drops
    for i in range(3):
        block_layout.add_circle((-0.15 + i * 0.15, 0.15), radius=0.05, dxfattribs={"layer": "SYMBOLS"})


def create_sink_block(block_layout: BlockLayout) -> None:
    """
    Create a sink/wastafel symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Sink basin (ellipse-like shape)
    block_layout.add_lwpolyline(
        points=[(-0.25, -0.15), (0.25, -0.15), (0.3, 0.15), (-0.3, 0.15)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )
    # Faucet (small vertical line)
    block_layout.add_line((0, 0.15), (0, 0.35), dxfattribs={"layer": "SYMBOLS"})


def create_cabinet_block(block_layout: BlockLayout) -> None:
    """
    Create a cabinet/kast symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Cabinet outline (rectangle)
    block_layout.add_lwpolyline(
        points=[(-0.3, -0.3), (0.3, -0.3), (0.3, 0.3), (-0.3, 0.3)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )
    # Door handle
    block_layout.add_circle((0.25, 0), radius=0.05, dxfattribs={"layer": "SYMBOLS"})


def create_temporary_cabinet_block(block_layout: BlockLayout) -> None:
    """
    Create a temporary cabinet (prov. kast) symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Cabinet outline (rectangle)
    block_layout.add_lwpolyline(
        points=[(-0.3, -0.3), (0.3, -0.3), (0.3, 0.3), (-0.3, 0.3)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )
    # Diagonal lines to indicate "temporary"
    block_layout.add_line((-0.3, -0.3), (0.3, 0.3), dxfattribs={"layer": "SYMBOLS"})
    block_layout.add_line((-0.3, 0.3), (0.3, -0.3), dxfattribs={"layer": "SYMBOLS"})


def create_bath_block(block_layout: BlockLayout) -> None:
    """
    Create a bathtub symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Bathtub (large rectangle with rounded corners)
    block_layout.add_lwpolyline(
        points=[(-0.4, -0.25), (0.4, -0.25), (0.4, 0.25), (-0.4, 0.25)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )
    # Drain (small circle)
    block_layout.add_circle((0, -0.15), radius=0.05, dxfattribs={"layer": "SYMBOLS"})


def create_stove_block(block_layout: BlockLayout) -> None:
    """
    Create a stove/cooktop symbol block.

    Args:
        block_layout: ezdxf block layout to add to
    """
    # Stove outline
    block_layout.add_lwpolyline(
        points=[(-0.3, -0.3), (0.3, -0.3), (0.3, 0.3), (-0.3, 0.3)],
        dxfattribs={"layer": "SYMBOLS", "closed": True},
    )
    # Burners (circles)
    for x in [-0.15, 0.15]:
        for y in [-0.15, 0.15]:
            block_layout.add_circle((x, y), radius=0.08, dxfattribs={"layer": "SYMBOLS"})

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

    # Create WC (toilet) block
    if "WC" not in blocks:
        wc_block = blocks.new(name="WC")
        create_wc_block(wc_block)

    # Create SHOWER block
    if "SHOWER" not in blocks:
        shower_block = blocks.new(name="SHOWER")
        create_shower_block(shower_block)

    # Create SINK block
    if "SINK" not in blocks:
        sink_block = blocks.new(name="SINK")
        create_sink_block(sink_block)

    # Create CABINET block
    if "CABINET" not in blocks:
        cabinet_block = blocks.new(name="CABINET")
        create_cabinet_block(cabinet_block)

    # Create TEMPORARY_CABINET block
    if "TEMPORARY_CABINET" not in blocks:
        temp_cabinet_block = blocks.new(name="TEMPORARY_CABINET")
        create_temporary_cabinet_block(temp_cabinet_block)

    # Create BATH block
    if "BATH" not in blocks:
        bath_block = blocks.new(name="BATH")
        create_bath_block(bath_block)

    # Create STOVE block
    if "STOVE" not in blocks:
        stove_block = blocks.new(name="STOVE")
        create_stove_block(stove_block)

    # Create WALL_HATCH block if it doesn't exist
    if "WALL_HATCH" not in blocks:
        wall_hatch = blocks.new(name="WALL_HATCH")
        create_wall_hatch(wall_hatch)


def get_block_name_for_symbol(symbol_type: str) -> str:
    """
    Get the block name for a given symbol type.

    Supports Dutch and English names for common fixtures.

    Args:
        symbol_type: Symbol type string (e.g., "door", "wc", "prov. kast")

    Returns:
        Block name to use
    """
    symbol_lower = symbol_type.lower().strip()

    mapping = {
        # Doors and windows
        "door": "DOOR",
        "deur": "DOOR",
        "window": "WINDOW",
        "raam": "WINDOW",
        "ramen": "WINDOW",

        # Stairs
        "staircase": "STAIRCASE",
        "stairs": "STAIRCASE",
        "stairwell": "STAIRCASE",
        "trap": "STAIRCASE",

        # Fixtures
        "fixture": "FIXTURE",

        # Dutch plumbing fixtures
        "wc": "WC",
        "toilet": "WC",
        "douche": "SHOWER",
        "shower": "SHOWER",
        "sink": "SINK",
        "wastafel": "SINK",
        "wastafels": "SINK",
        "bad": "BATH",
        "bath": "BATH",
        "bathtub": "BATH",

        # Cabinets
        "kast": "CABINET",
        "cabinet": "CABINET",
        "closet": "CABINET",
        "prov. kast": "TEMPORARY_CABINET",
        "prov.kast": "TEMPORARY_CABINET",
        "provisory cabinet": "TEMPORARY_CABINET",

        # Appliances
        "stove": "STOVE",
        "oven": "STOVE",
        "cook": "STOVE",
        "fornuis": "STOVE",
        "oven": "STOVE",
    }

    # Try exact match first
    if symbol_lower in mapping:
        return mapping[symbol_lower]

    # Try prefix match for longer terms
    for key, block_name in mapping.items():
        if key in symbol_lower or symbol_lower in key:
            return block_name

    # Default to FIXTURE
    return "FIXTURE"
