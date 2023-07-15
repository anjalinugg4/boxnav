from argparse import ArgumentParser, Namespace
from math import radians
from pathlib import Path

import matplotlib.pyplot as plt
from celluloid import Camera

from box.box import Pt, aligned_box
from box.boxenv import BoxEnv
from box.boxnavigator import PerfectNavigator, WanderingNavigator
from box.boxunreal import UENavigatorWrapper

# TODO: this should probably be a command line argument (pass in a list of coordinates)
# route 2, uses path w/ water fountain & stairs
boxes = [
    aligned_box(left=4640, right=5240, lower=110, upper=1510, target=(4940, 870)),
    aligned_box(left=3720, right=5240, lower=700, upper=1040, target=(4100, 870)),
    aligned_box(left=3720, right=4120, lower=350, upper=1040, target=(4100, 400)),
    aligned_box(left=110, right=4120, lower=240, upper=540, target=(255, 390)),
    aligned_box(left=110, right=400, lower=-1980, upper=540, target=(255, -1900)),
    aligned_box(left=-1550, right=400, lower=-1980, upper=-1650, target=(-825, -1815)),
    aligned_box(left=-950, right=-700, lower=-1980, upper=3320, target=(-825, 2485)),
    aligned_box(left=-950, right=230, lower=2150, upper=2820, target=(200, 2485)),
]


def check_path(path: Path) -> None:
    # TODO: check for existing files
    pass


def simulate(args: Namespace, dataset_path: str) -> None:
    """Create and update the box environment and run the navigator."""

    box_env = BoxEnv(boxes)

    starting_box = boxes[0]
    initial_x = starting_box.left + starting_box.width / 2
    initial_y = starting_box.lower + 50
    initial_position = Pt(initial_x, initial_y)
    initial_rotation = radians(90)

    if args.navigator == "wandering":
        NavigatorConstructor = WanderingNavigator
    elif args.navigator == "perfect":
        NavigatorConstructor = PerfectNavigator
    else:
        raise ValueError("Invalid value for navigator.")

    agent = NavigatorConstructor(initial_position, initial_rotation, box_env)

    # Wrap the agent if we want to connect to Unreal Engine
    if args.ue:
        agent = UENavigatorWrapper(
            agent,
            args.save_images,
            args.py_port,
            args.ue_port,
        )

    fig, ax = plt.subplots()
    camera = Camera(fig)
    while not agent.at_final_target() and agent.num_actions_taken() < args.max_actions:
        try:
            _, _ = agent.take_action()
        except TimeoutError as e:
            print(e)
            if isinstance(agent, UENavigatorWrapper):
                agent.ue5.close_osc()
            raise SystemExit

        # except ValueError as e:
        #     print(e)
        #     break

        if args.anim_ext:
            # TODO: Rotate axis so that agent is always facing up
            box_env.display(ax)
            agent.display(ax, 300)
            ax.invert_xaxis()
            camera.snap()

    if isinstance(agent, UENavigatorWrapper):
        agent.ue5.close_osc()

    print("Simulation complete.", end=" ")

    num_actions = agent.num_actions_taken()
    if agent.at_final_target():
        print(f"Agent reached final target in {num_actions} actions.")
    else:
        print(f"Agent was unable to reach final target within {num_actions} actions.")

    if args.anim_ext:
        output_filename = None
        num = 1
        while not output_filename or Path(output_filename).exists():
            output_filename = f"output_{num}.{args.anim_ext}"
            num += 1
        anim = camera.animate()
        anim.save(output_filename)
        print(f"Animation saved to {output_filename}.")


def main():
    """Parse arguments and run simulation."""

    argparser = ArgumentParser("Navigate around a box environment.")

    #
    # Required arguments
    #

    argparser.add_argument("navigator", type=str, help="Navigator to run.")

    #
    # Optional arguments
    #

    argparser.add_argument("--anim_ext", type=str, help="Output format for animation.")

    argparser.add_argument(
        "--max_actions", type=int, default=10, help="Maximum allowed actions."
    )

    argparser.add_argument(
        "--save_images",
        type=str,
        help="Directory in which images should be saved (no images saved otherwise).",
    )

    argparser.add_argument(
        "--ue", action="store_true", help="Connect and send command to Unreal Engine."
    )

    argparser.add_argument(
        "--py_port", type=int, default=7001, help="Python OSC server port."
    )

    argparser.add_argument(
        "--ue_port", type=int, default=7447, help="Unreal Engine OSC server port."
    )

    argparser.add_argument(
        "--resolution", type=str, help="Set resolution of images as ResX."
    )

    args = argparser.parse_args()

    possible_navigators = ["wandering", "perfect"]
    if args.navigator not in possible_navigators:
        raise ValueError(
            f"Invalid navigator type: {args.navigator}. Possible options: {'|'.join(possible_navigators)}"
        )

    if args.save_images and not args.ue:
        raise ValueError("Cannot collect data without connecting to Unreal Engine.")

    if args.resolution and not args.ue:
        raise ValueError("Resolution is unnecessary without Unreal Engine.")

    if args.save_images:
        check_path(args.save_images)

    simulate(args, args.save_images)


if __name__ == "__main__":
    main()
