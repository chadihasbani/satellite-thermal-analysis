"""Rectangular spacecraft bus geometry for enhanced single-node heating.

Coordinate conventions
----------------------
Body frame is right-handed. Dimensions are:

    length_m  along body +X
    width_m   along body +Y
    height_m  along body +Z

Six outward face normals in the body frame are ±X, ±Y, ±Z. Face areas are
derived from the three dimensions so opposite faces share area and the six
faces are not double-counted:

    A_±x = width * height
    A_±y = length * height
    A_±z = length * width

    A_total = 2 * (width*height + length*height + length*width)

Optical properties may be uniform or face-specific. Solar panels drawn in the
3D view are illustrative only and are not thermal surfaces in this module.

Classification: uniform optical defaults remain illustrative modelling
assumptions (C). Checkpoint 5 may supply CDS Rev 14.1 envelope dimensions for
CubeSat-inspired presets; masses and effective cp used with those envelopes are
still illustrative unless labelled otherwise. Visual solar panels are never
thermal faces.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.validation import (
    require_finite_number,
    require_fraction,
    require_positive,
)

FACE_NAMES: tuple[str, ...] = ("+x", "-x", "+y", "-y", "+z", "-z")

_BODY_NORMALS: dict[str, tuple[float, float, float]] = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
}


@dataclass(frozen=True)
class FaceOpticalProperties:
    """Solar absorptivity and infrared emissivity for one exterior face."""

    absorptivity: float
    emissivity: float

    def validated(self) -> "FaceOpticalProperties":
        return FaceOpticalProperties(
            absorptivity=require_fraction("absorptivity", self.absorptivity),
            emissivity=require_fraction("emissivity", self.emissivity),
        )


@dataclass(frozen=True)
class RectangularBusGeometry:
    """Closed rectangular bus with six exterior faces.

    Default 0.1 m cube: each face is 0.01 m² and total exterior area is
    0.06 m², matching the Version 1.0 projected / radiating area defaults so
    enhanced fixed-inertial sunlight can reproduce the legacy solar and
    radiation terms when only one face sees the Sun.
    """

    length_m: float = 0.1
    width_m: float = 0.1
    height_m: float = 0.1
    absorptivity: float = 0.60
    emissivity: float = 0.80
    face_optics: dict[str, FaceOpticalProperties] | None = None

    def validated(self) -> "RectangularBusGeometry":
        length = require_positive("length_m", self.length_m)
        width = require_positive("width_m", self.width_m)
        height = require_positive("height_m", self.height_m)
        alpha = require_fraction("absorptivity", self.absorptivity)
        epsilon = require_fraction("emissivity", self.emissivity)
        optics = self.face_optics
        if optics is not None:
            cleaned: dict[str, FaceOpticalProperties] = {}
            for name, props in optics.items():
                if name not in FACE_NAMES:
                    raise ValueError(f"Unknown face name {name!r}.")
                cleaned[name] = props.validated()
            optics = cleaned
        return RectangularBusGeometry(
            length_m=length,
            width_m=width,
            height_m=height,
            absorptivity=alpha,
            emissivity=epsilon,
            face_optics=optics,
        )

    def face_area_m2(self, face_name: str) -> float:
        """Area of one named face, derived from body dimensions."""
        settings = self.validated()
        name = face_name.lower()
        if name not in FACE_NAMES:
            raise ValueError(f"Unknown face name {face_name!r}.")
        if name in ("+x", "-x"):
            return settings.width_m * settings.height_m
        if name in ("+y", "-y"):
            return settings.length_m * settings.height_m
        return settings.length_m * settings.width_m

    def total_exterior_area_m2(self) -> float:
        """Sum of all six face areas (no double-counting)."""
        settings = self.validated()
        return 2.0 * (
            settings.width_m * settings.height_m
            + settings.length_m * settings.height_m
            + settings.length_m * settings.width_m
        )

    def body_normal(self, face_name: str) -> tuple[float, float, float]:
        """Outward unit normal of a face in the body frame."""
        name = face_name.lower()
        if name not in _BODY_NORMALS:
            raise ValueError(f"Unknown face name {face_name!r}.")
        return _BODY_NORMALS[name]

    def optics_for_face(self, face_name: str) -> FaceOpticalProperties:
        """Optical properties for one face (face-specific or uniform default)."""
        settings = self.validated()
        name = face_name.lower()
        if name not in FACE_NAMES:
            raise ValueError(f"Unknown face name {face_name!r}.")
        if settings.face_optics is not None and name in settings.face_optics:
            return settings.face_optics[name]
        return FaceOpticalProperties(
            absorptivity=settings.absorptivity,
            emissivity=settings.emissivity,
        ).validated()


def rotate_vector(
    vector: tuple[float, float, float],
    body_x: tuple[float, float, float],
    body_y: tuple[float, float, float],
    body_z: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Map a body-frame vector into the inertial frame using body axis columns.

    If body_x/y/z are the body axes expressed in inertial coordinates, then
    v_inertial = v_x * body_x + v_y * body_y + v_z * body_z.
    """
    vx = require_finite_number("vector[0]", vector[0])
    vy = require_finite_number("vector[1]", vector[1])
    vz = require_finite_number("vector[2]", vector[2])
    return (
        vx * body_x[0] + vy * body_y[0] + vz * body_z[0],
        vx * body_x[1] + vy * body_y[1] + vz * body_z[1],
        vx * body_x[2] + vy * body_y[2] + vz * body_z[2],
    )


def face_normal_inertial(
    geometry: RectangularBusGeometry,
    face_name: str,
    body_x: tuple[float, float, float],
    body_y: tuple[float, float, float],
    body_z: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Outward face normal expressed in the inertial frame."""
    settings = geometry.validated()
    return rotate_vector(settings.body_normal(face_name), body_x, body_y, body_z)
