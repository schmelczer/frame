# Dithering Test Suite for 6-Color E-Ink Display
from .dither_algorithms import (
    apply_dithering,
    get_algorithm_names,
    DITHER_ALGORITHMS,
    PALETTE_RGB,
    PALETTE_NAMES,
)

__all__ = [
    'apply_dithering',
    'get_algorithm_names',
    'DITHER_ALGORITHMS',
    'PALETTE_RGB',
    'PALETTE_NAMES',
]
