import time
import logging

import numpy as np
from autoscript_sdb_microscope_client import SdbMicroscopeClient
from autoscript_sdb_microscope_client.enumerations import (
    ManipulatorCoordinateSystem,
    ManipulatorSavedPosition,
)
from autoscript_sdb_microscope_client.structures import (
    ManipulatorPosition,
    MoveSettings,
    StagePosition,
)
from fibsem.structures import BeamType, MicroscopeSettings

############################## NEEDLE ##############################


def insert_needle(
    microscope: SdbMicroscopeClient,
    insert_position: ManipulatorSavedPosition = ManipulatorSavedPosition.PARK,
) -> None:
    """Insert the needle to the selected saved insert position.

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        insert_position (ManipulatorSavedPosition, optional): saved needle position. Defaults to ManipulatorSavedPosition.PARK.
    """
    needle = microscope.specimen.manipulator
    # logging.info(f"inserting needle to {insert_position.explain} position.")
    insert_position = needle.get_saved_position(
        insert_position, ManipulatorCoordinateSystem.RAW
    )
    needle.insert(insert_position)
    logging.info(f"inserted needle to {insert_position}.")


def retract_multichem(microscope: SdbMicroscopeClient) -> None:
    # Retract the multichem
    logging.info(f"retracting multichem")
    multichem = microscope.gas.get_multichem()
    multichem.retract()
    logging.info(f"retract multichem complete")

    return


def retract_needle(microscope: SdbMicroscopeClient) -> None:
    """Retract the needle and multichem, preserving the correct park position."""

    # retract multichem
    retract_multichem(microscope)

    # Retract the needle, preserving the correct parking postiion
    needle = microscope.specimen.manipulator
    # current_position = needle.current_position
    park_position = needle.get_saved_position(
        ManipulatorSavedPosition.PARK, ManipulatorCoordinateSystem.RAW
    )

    # To prevent collisions with the sample; first retract in z, then y, then x
    logging.info(
        f"retracting needle to {park_position}"
    )  # TODO: replace with move_needle_relative...
    # needle.relative_move(
    #     ManipulatorPosition(z=park_position.z - current_position.z)
    # )  # noqa: E501
    # needle.relative_move(
    #     ManipulatorPosition(y=park_position.y - current_position.y)
    # )  # noqa: E501
    # needle.relative_move(
    #     ManipulatorPosition(x=park_position.x - current_position.x)
    # )  # noqa: E501
    needle.absolute_move(park_position)
    time.sleep(1)  # AutoScript sometimes throws errors if you retract too quick?
    logging.info(f"retracting needle...")
    needle.retract()
    logging.info(f"retract needle complete")


def move_needle_to_eucentric_position_offset(
    microscope: SdbMicroscopeClient, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0
) -> None:
    """Move the needle to a position offset, based on the eucentric position

    Args:
        microscope (SdbMicroscopeClient): AutoScript Microscope Instance
        dx (float, optional): x-axis offset, image coordinates. Defaults to 0.0.
        dy (float, optional): y-axis offset, image coordinates. Defaults to 0.0.
        dz (float, optional): z-axis offset, image coordinates. Defaults to 0.0.
    """

    # move to relative to the eucentric point
    eucentric_position = microscope.specimen.manipulator.get_saved_position(
        ManipulatorSavedPosition.EUCENTRIC, ManipulatorCoordinateSystem.STAGE
    )
    yz_move = z_corrected_needle_movement(
        dz, microscope.specimen.stage.current_position.t
    )
    eucentric_position.x += dx
    eucentric_position.y += yz_move.y + dy
    eucentric_position.z += yz_move.z  # RAW, up = negative, STAGE: down = negative
    microscope.specimen.manipulator.absolute_move(eucentric_position)


def x_corrected_needle_movement(
    expected_x: float
) -> ManipulatorPosition:
    """Calculate the corrected needle movement to move in the x-axis.

    Args:
        expected_x (float): distance along the x-axis (image coordinates)
    Returns:
        ManipulatorPosition: x-corrected needle movement (relative position)
    """
    return ManipulatorPosition(x=expected_x, y=0, z=0)  # no adjustment needed


def y_corrected_needle_movement(
    expected_y: float, stage_tilt: float
) -> ManipulatorPosition:
    """Calculate the corrected needle movement to move in the y-axis.

    Args:
        expected_x (float): distance along the y-axis (image coordinates)
        stage_tilt (float, optional): stage tilt.

    Returns:
        ManipulatorPosition: y-corrected needle movement (relative position)
    """
    y_move = +np.cos(stage_tilt) * expected_y
    z_move = +np.sin(stage_tilt) * expected_y
    return ManipulatorPosition(x=0, y=y_move, z=z_move)


def z_corrected_needle_movement(
    expected_z: float, stage_tilt: float
) -> ManipulatorPosition:
    """Calculate the corrected needle movement to move in the z-axis.

    Args:
        expected_x (float): distance along the z-axis (image coordinates)
        stage_tilt (float, optional): stage tilt.

    Returns:
        ManipulatorPosition: z-corrected needle movement (relative position)
    """
    y_move = -np.sin(stage_tilt) * expected_z
    z_move = +np.cos(stage_tilt) * expected_z
    return ManipulatorPosition(x=0, y=y_move, z=z_move)


def move_needle_relative_with_corrected_movement(
    microscope: SdbMicroscopeClient,
    dx: float,
    dy: float,
    beam_type: BeamType = BeamType.ELECTRON,
) -> None:
    """Calculate the required corrected needle movements based on the BeamType to move in the desired image coordinates.
    Then move the needle relatively.

    BeamType.ELECTRON:  move in x, y (raw coordinates)
    BeamType.ION:       move in x, z (raw coordinates)

    Args:
        microscope (SdbMicroscopeClient): autoScript microscope instance
        dx (float): distance along the x-axis (image coordinates)
        dy (float): distance along the y-axis (image corodinates)
        beam_type (BeamType, optional): the beam type to move in. Defaults to BeamType.ELECTRON.
    """

    needle = microscope.specimen.manipulator
    stage_tilt = microscope.specimen.stage.current_position.t

    # xy
    if beam_type is BeamType.ELECTRON:
        x_move = x_corrected_needle_movement(expected_x=dx)
        yz_move = y_corrected_needle_movement(dy, stage_tilt=stage_tilt)

    # xz,
    if beam_type is BeamType.ION:

        x_move = x_corrected_needle_movement(expected_x=dx)
        yz_move = z_corrected_needle_movement(expected_z=dy, stage_tilt=stage_tilt)

    # move needle (relative)
    needle_position = ManipulatorPosition(x=x_move.x, y=yz_move.y, z=yz_move.z)
    logging.info(f"Moving needle: {needle_position}.")
    needle.relative_move(needle_position)

    return


############################## STAGE ##############################


def move_flat_to_beam(
    microscope: SdbMicroscopeClient,
    settings: dict,
    beam_type: BeamType = BeamType.ELECTRON,
) -> None:
    """Make the sample surface flat to the electron or ion beam.

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        settings (dict): settings dictionary
        beam_type (BeamType, optional): beam type to move flat to. Defaults to BeamType.ELECTRON.
    """

    # stage = microscope.specimen.stage
    # stage_settings = MoveSettings(rotate_compucentric=True)

    # v2
    # settings_v2 = MicroscopeSettings()
    # stage_settings = settings_v2.system.stage

    # if beam_type is BeamType.ELECTRON:
    #     rotation = np.deg2rad(stage_settings.rotation_flat_to_electron)
    #     tilt = np.deg2rad(stage_settings.tilt_flat_to_electron)

    # if beam_type is BeamType.ION:
    #     rotation = np.deg2rad(stage_settings.rotation_flat_to_ion)
    #     tilt = np.deg2rad(stage_settings.tilt_flat_to_ion - stage_settings.tilt_flat_to_electron)

    pretilt_angle = settings["system"]["pretilt_angle"]  # 27

    if beam_type is BeamType.ELECTRON:
        rotation = settings["system"]["stage_rotation_flat_to_electron"]
        tilt = np.deg2rad(pretilt_angle)
    if beam_type is BeamType.ION:
        rotation = settings["system"]["stage_rotation_flat_to_ion"]
        tilt = np.deg2rad(settings["system"]["stage_tilt_flat_to_ion"] - pretilt_angle)
    rotation = np.deg2rad(rotation)

    logging.info(f"moving flat to {beam_type.name}")

    # TODO: check why we can't just use safe_absolute_stage_movement
    # I think it is because we want to maintain position, and only tilt/rotate
    # # why isnt it the same as going to the same xyz with new rt?

    # updated save rotation move
    stage_position = StagePosition(r=rotation, t=tilt)
    safe_absolute_stage_movement(microscope, stage_position)

    # safe_rotation_movement(microscope, stage_position)

    # if abs(np.rad2deg(rotation - stage.current_position.r)) % 360 > 90:
    #     stage.absolute_move(StagePosition(t=0), stage_settings)  # just in case
    #     logging.info(f"tilting to flat for large rotation.")

    # logging.info(f"rotation: {rotation:.4f},  tilt: {tilt:.4f}")
    # stage.absolute_move(StagePosition(r=rotation, t=tilt), stage_settings)

    return


def move_flat_to_beam_v2(
    microscope: SdbMicroscopeClient,
    settings: MicroscopeSettings,
    beam_type: BeamType = BeamType.ELECTRON,
) -> None:
    """Make the sample surface flat to the electron or ion beam.

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        settings (MicroscopeSettings): microscope settings
        beam_type (BeamType, optional): beam type to move flat to. Defaults to BeamType.ELECTRON.
    """

    stage_settings = settings.system.stage

    if beam_type is BeamType.ELECTRON:
        rotation = np.deg2rad(stage_settings.rotation_flat_to_electron)
        tilt = np.deg2rad(stage_settings.tilt_flat_to_electron)

    if beam_type is BeamType.ION:
        rotation = np.deg2rad(stage_settings.rotation_flat_to_ion)
        tilt = np.deg2rad(
            stage_settings.tilt_flat_to_ion - stage_settings.tilt_flat_to_electron
        )

    # updated safe rotation move
    logging.info(f"moving flat to {beam_type.name}")
    stage_position = StagePosition(r=rotation, t=tilt)
    safe_absolute_stage_movement(microscope, stage_position)

    return


# TODO: make these consistenly use degrees or radians...
def rotation_angle_is_larger(angle1: float, angle2: float, atol: float = 90) -> bool:
    """Check the rotation angles are large

    Args:
        angle1 (float): angle1 (radians)
        angle2 (float): angle2 (radians)
        atol : tolerance (degrees)

    Returns:
        bool: rotation angle is larger than atol
    """

    return angle_difference(angle1, angle2) > (np.deg2rad(atol))


def rotation_angle_is_smaller(angle1: float, angle2: float, atol: float = 5) -> bool:
    """Check the rotation angles are large

    Args:
        angle1 (float): angle1 (radians)
        angle2 (float): angle2 (radians)
        atol : tolerance (degrees)

    Returns:
        bool: rotation angle is smaller than atol
    """

    return angle_difference(angle1, angle2) < (np.deg2rad(atol))


def angle_difference(angle1: float, angle2: float) -> float:
    """Return the difference between two angles, accounting for greater than 360, less than 0 angles

    Args:
        angle1 (float): angle1 (radians)
        angle2 (float): angle2 (radians)

    Returns:
        float: _description_
    """
    return min(np.abs(2 * np.pi + angle1 - angle2), np.abs(angle1 - angle2)) % (
        2 * np.pi
    )


def safe_rotation_movement(
    microscope: SdbMicroscopeClient, stage_position: StagePosition
):
    """Tilt the stage flat when performing a large rotation to prevent collision.

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        stage_position (StagePosition): desired stage position.
    """
    stage = microscope.specimen.stage
    stage_settings = MoveSettings(rotate_compucentric=True)

    # tilt flat for large rotations to prevent collisions
    if rotation_angle_is_larger(stage_position.r, stage.current_position.r):

        stage.absolute_move(
            StagePosition(
                t=np.deg2rad(0), 
                coordinate_system=stage_position.coordinate_system
            ),
            stage_settings,
        )
        logging.info(f"tilting to flat for large rotation.")

    return


def safe_absolute_stage_movement(
    microscope: SdbMicroscopeClient, stage_position: StagePosition
) -> None:
    """Move the stage to the desired position in a safe manner, using compucentric rotation.
    Supports movements in the stage_position coordinate system

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        stage_position (StagePosition): desired stage position

    Returns:
        StagePosition: _description_
    """

    stage = microscope.specimen.stage
    stage_settings = MoveSettings(rotate_compucentric=True)

    # TODO: replace
    # tilt flat for large rotations to prevent collisions
    input("TESTING STOP POINT: SAFE ROTATION")
    safe_rotation_movement(microscope, stage_position)

    # if abs(np.rad2deg(stage_position.r - stage.current_position.r)) % 360 > 90:
    #     stage.absolute_move(
    #         StagePosition(
    #             t=np.deg2rad(0), coordinate_system=stage_position.coordinate_system
    #         ),
    #         stage_settings,
    #     )
    #     logging.info(f"tilting to flat for large rotation.")

    stage.absolute_move(
        StagePosition(
            r=stage_position.r, coordinate_system=stage_position.coordinate_system
        ),
        stage_settings,
    )
    logging.info(f"safe moving to {stage_position}")
    stage.absolute_move(stage_position, stage_settings)
    logging.info(f"safe movement complete.")

    return


def x_corrected_stage_movement(
    expected_x: float,
) -> StagePosition:
    """Calculate the x corrected stage movement.

    Args:
        expected_x (float): distance along x-axis

    Returns:
        StagePosition: x corrected stage movement (relative position)
    """
    return StagePosition(x=expected_x, y=0, z=0)


def y_corrected_stage_movement(
    microscope: SdbMicroscopeClient,
    settings: dict,
    expected_y: float,
    beam_type: BeamType = BeamType.ELECTRON,
) -> StagePosition:
    """Calculate the y corrected stage movement, corrected for the additional tilt of the sample holder (pre-tilt angle).

    Args:
        microscope (SdbMicroscopeClient, optional): autoscript microscope instance
        settings (dict, optional): settings dict
        expected_y (float, optional): distance along y-axis.
        beam_type (BeamType, optional): beam_type to move in. Defaults to BeamType.ELECTRON.

    Returns:
        StagePosition: y corrected stage movement (relative position)
    """

    # all angles in radians
    pretilt_angle = np.deg2rad(settings["system"]["pretilt_angle"])
    stage_tilt_flat_to_ion = np.deg2rad(settings["system"]["stage_tilt_flat_to_ion"])

    stage_rotation_flat_to_eb = np.deg2rad(
        settings["system"]["stage_rotation_flat_to_electron"]
    ) % (2 * np.pi)
    stage_rotation_flat_to_ion = np.deg2rad(
        settings["system"]["stage_rotation_flat_to_ion"]
    ) % (2 * np.pi)
    stage_rotation = microscope.specimen.stage.current_position.r % (2 * np.pi)
    stage_tilt = microscope.specimen.stage.current_position.t

    # pretilt angle depends on rotation
    if np.isclose(stage_rotation, stage_rotation_flat_to_eb, atol=np.deg2rad(5)):
        PRETILT_SIGN = 1.0
    if np.isclose(stage_rotation, stage_rotation_flat_to_ion, atol=np.deg2rad(5)):
        PRETILT_SIGN = -1.0

    corrected_pretilt_angle = PRETILT_SIGN * pretilt_angle

    # total tilt adjustment (difference between perspective view and sample coordinate system)
    if beam_type == BeamType.ELECTRON:
        tilt_adjustment = -corrected_pretilt_angle
        SCALE_FACTOR = 1.0  # 0.78342  # patented technology
    elif beam_type == BeamType.ION:
        tilt_adjustment = -corrected_pretilt_angle - stage_tilt_flat_to_ion
        SCALE_FACTOR = 1.0

    # the amount the sample has to move in the y-axis
    y_sample_move = (expected_y * SCALE_FACTOR) / np.cos(stage_tilt + tilt_adjustment)

    # the amount the stage has to move in each axis
    y_move = y_sample_move * np.cos(corrected_pretilt_angle)
    z_move = y_sample_move * np.sin(corrected_pretilt_angle)

    logging.info(f"rotation:  {microscope.specimen.stage.current_position.r} rad")
    logging.info(f"stage_tilt: {np.rad2deg(stage_tilt)}deg")
    logging.info(f"tilt_adjustment: {np.rad2deg(tilt_adjustment)}deg")
    logging.info(f"corrected_pretilt_angle: {np.rad2deg(corrected_pretilt_angle)}deg")
    logging.info(f"expected_y: {expected_y:.3e}m")
    logging.info(f"y_sample_move: {y_sample_move:.3e}m")
    logging.info(f"y-move: {y_move:.3e}m, z-move: {z_move:.3e}m")

    return StagePosition(x=0, y=y_move, z=z_move)


def y_corrected_stage_movement_v2(
    microscope: SdbMicroscopeClient,
    settings: MicroscopeSettings,
    expected_y: float,
    beam_type: BeamType = BeamType.ELECTRON,
) -> StagePosition:
    """Calculate the y corrected stage movement, corrected for the additional tilt of the sample holder (pre-tilt angle).

    Args:
        microscope (SdbMicroscopeClient, optional): autoscript microscope instance
        settings (MicroscopeSettings): microscope settings
        expected_y (float, optional): distance along y-axis.
        beam_type (BeamType, optional): beam_type to move in. Defaults to BeamType.ELECTRON.

    Returns:
        StagePosition: y corrected stage movement (relative position)
    """

    # all angles in radians
    stage_tilt_flat_to_electron = np.deg2rad(
        settings.system.stage.tilt_flat_to_electron
    )
    stage_tilt_flat_to_ion = np.deg2rad(settings.system.stage.tilt_flat_to_ion)

    stage_rotation_flat_to_eb = np.deg2rad(
        settings.system.stage.rotation_flat_to_electron
    ) % (2 * np.pi)
    stage_rotation_flat_to_ion = np.deg2rad(
        settings.system.stage.rotation_flat_to_ion
    ) % (2 * np.pi)

    # current stage position
    stage_rotation = microscope.specimen.stage.current_position.r % (2 * np.pi)
    stage_tilt = microscope.specimen.stage.current_position.t

    # pretilt angle depends on rotation
    if rotation_angle_is_smaller(stage_rotation, stage_rotation_flat_to_eb, atol=5):
    # if np.isclose(stage_rotation, stage_rotation_flat_to_eb, atol=np.deg2rad(5)):
        PRETILT_SIGN = 1.0
    if rotation_angle_is_smaller(stage_rotation, stage_rotation_flat_to_ion, atol=5):
    # if np.isclose(stage_rotation, stage_rotation_flat_to_ion, atol=np.deg2rad(5)):
        PRETILT_SIGN = -1.0

    # TODO: what happens if we arent close?

    corrected_pretilt_angle = PRETILT_SIGN * stage_tilt_flat_to_electron

    # perspective tilt adjustment (difference between perspective view and sample coordinate system)
    if beam_type == BeamType.ELECTRON:
        perspective_tilt_adjustment = -corrected_pretilt_angle
        SCALE_FACTOR = 1.0  # 0.78342  # patented technology
    elif beam_type == BeamType.ION:
        perspective_tilt_adjustment = -corrected_pretilt_angle - stage_tilt_flat_to_ion
        SCALE_FACTOR = 1.0

    # the amount the sample has to move in the y-axis
    y_sample_move = (expected_y * SCALE_FACTOR) / np.cos(stage_tilt + perspective_tilt_adjustment)

    # the amount the stage has to move in each axis
    y_move = y_sample_move * np.cos(corrected_pretilt_angle)
    z_move = y_sample_move * np.sin(corrected_pretilt_angle)

    return StagePosition(x=0, y=y_move, z=z_move)


def move_stage_relative_with_corrected_movement(
    microscope: SdbMicroscopeClient,
    settings: dict,
    dx: float,
    dy: float,
    beam_type: BeamType,
) -> None:
    """Calculate the corrected stage movements based on the beam_type, and then move the stage relatively.

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        settings (dict): settings dictionary
        dx (float): distance along the x-axis (image coordinates)
        dy (float): distance along the y-axis (image coordinates)
        beam_type (BeamType): beam type to move in
    """
    stage = microscope.specimen.stage

    # calculate stage movement
    x_move = x_corrected_stage_movement(dx, stage_tilt=stage.current_position.t)
    yz_move = y_corrected_stage_movement(
        microscope=microscope,
        settings=settings,
        expected_y=dy,
        beam_type=beam_type,
    )

    # move stage
    stage_position = StagePosition(x=x_move.x, y=yz_move.y, z=yz_move.z)
    logging.info(f"moving stage: {stage_position}")
    stage.relative_move(stage_position)

    return


def move_stage_relative_with_corrected_movement_v2(
    microscope: SdbMicroscopeClient,
    settings: MicroscopeSettings,
    dx: float,
    dy: float,
    beam_type: BeamType,
) -> None:
    """Calculate the corrected stage movements based on the beam_type, and then move the stage relatively.

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        settings (MicroscopeSettings): microscope settings
        dx (float): distance along the x-axis (image coordinates)
        dy (float): distance along the y-axis (image coordinates)
        beam_type (BeamType): beam type to move in
    """
    stage = microscope.specimen.stage

    # calculate stage movement
    x_move = x_corrected_stage_movement(dx)
    yz_move = y_corrected_stage_movement_v2(
        microscope=microscope,
        settings=settings,
        expected_y=dy,
        beam_type=beam_type,
    )

    # move stage
    stage_position = StagePosition(x=x_move.x, y=yz_move.y, z=yz_move.z)
    logging.info(f"moving stage: {stage_position}")
    stage.relative_move(stage_position)

    return


def move_stage_eucentric_correction(microscope: SdbMicroscopeClient, dy: float) -> None:
    """Move the stage vertically to correct eucentric point

    Args:
        microscope (SdbMicroscopeClient): autoscript microscope instance
        dy (float): distance in y-axis (image coordinates)
    """
    z_move = dy / np.cos(np.deg2rad(38))  # MAGIC NUMBER

    move_settings = MoveSettings(link_z_y=True)
    z_move = StagePosition(z=z_move, coordinate_system="Specimen")
    microscope.specimen.stage.relative_move(z_move, move_settings)
