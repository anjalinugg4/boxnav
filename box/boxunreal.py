from math import degrees
from pathlib import Path
from time import sleep

from ue5osc import Communicator

from .boxnavigator import Action, BoxNavigatorBase


class UENavigatorWrapper:
    """A wrapper for navigators that facilitates coordination with UnrealEngine 5."""

    def __init__(
        self,
        navigator: BoxNavigatorBase,
        dataset_path: str | None,
        py_server_port: int,
        ue_server_port: int,
    ) -> None:
        self.ue5 = Communicator("127.0.0.1", ue_server_port, py_server_port)

        self.navigator = navigator
        self.dataset_path = Path(dataset_path).resolve() if dataset_path else None

        if self.dataset_path:
            self.dataset_path.mkdir(parents=True, exist_ok=True)

        self.images_saved = 0

        try:
            # Sync UE and boxsim
            self.sync_positions()
            self.sync_rotation()
        except TimeoutError:
            self.ue5.close_osc()
            print(
                "Received Timeout Error from OSC Communicator.",
                "Check if UE packaged game is running.",
            )
            raise SystemExit

        self.reset()

    def reset(self) -> None:
        """Resets agent to its initial position."""
        return self.ue5.reset()

    def __getattr__(self, attr):
        """Dispatch unknown method calls to navigator object."""
        return getattr(self.navigator, attr)

    def sync_positions(self) -> None:
        """Move UE agent to match boxsim agent."""

        # Get z position from UE
        _, _, unreal_z = self.ue5.get_location()

        # Get x, y position from boxsim
        x, y = self.navigator.position.xy()

        self.ue5.set_location(x, y, unreal_z)

    # def sync_box_position_to_unreal(self) -> None:
    #     """Move Boxsim agent to match Unreal Agent Position"""
    #     unrealX, unrealY, _ = self.ue5.get_camera_location(0)
    #     self.navigator.move(Pt(unrealX, unrealY))

    def sync_rotation(self) -> None:
        """Sync UE agent location to box agent."""
        # Conversion from Box to unreal location is (180 - boxYaw) = unrealYaw
        unreal_yaw: float = degrees(self.navigator.rotation)
        self.ue5.set_yaw(unreal_yaw)

    def take_action(self) -> tuple[Action, Action]:
        """Execute action in the navigator and in the UE agent.

        Returns:
            tuple[Action, Action]: return action taken and correct action.

        Raises:
            RuntimeError: If the action is not defined.
        """

        action_taken, correct_action = self.navigator.take_action()
        if self.dataset_path:
            self.save_image(correct_action)
        else:
            # A short delay to allow UE to render the scene after teleport
            sleep(0.1)

        if action_taken == Action.FORWARD:
            self.ue5.move_forward(self.navigator.translation_increment)
        elif action_taken == Action.BACKWARD:
            self.ue5.move_backward(self.navigator.translation_increment)
        elif action_taken == Action.ROTATE_LEFT:
            self.sync_rotation()
        elif action_taken == Action.ROTATE_RIGHT:
            self.sync_rotation()
        else:
            raise RuntimeError(f"Undefined action: {action_taken}")

        return action_taken, correct_action

    def save_image(self, action: Action) -> None:
        # Rotations are swapped in UE
        if action == Action.ROTATE_LEFT:
            action = Action.ROTATE_RIGHT
        elif action == Action.ROTATE_RIGHT:
            action = Action.ROTATE_LEFT

        # Generate the next filename
        image_filepath = (
            f"{self.dataset_path}/" f"{self.images_saved:06}_{str(action).lower()}.png"
        )

        self.images_saved += 1

        # Let teleport complete, save the image, then wait for image save
        sleep(0.25)
        self.ue5.save_image(image_filepath)
        # TODO: maybe loop until the image exists?
        sleep(0.25)
