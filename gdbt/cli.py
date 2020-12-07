#!/usr/bin/env python3
import time
import typing

import click
import halo  # type: ignore
import rich.console
import rich.traceback

import gdbt
import gdbt.errors
import gdbt.provider.provider
import gdbt.state.state
import gdbt.state.diff
import gdbt.state.plan
import gdbt.stencil.load

console = rich.console.Console(highlight=False)
rich.traceback.install()


@click.group()
def main():
    pass


@click.command()
def version() -> None:
    """Get GDBT version"""
    console.print(f"GDBT version {gdbt.__version__}")


@click.command()
@click.option(
    "-c",
    "--config-dir",
    type=click.STRING,
    default=".",
    help="Configuration directory",
)
def plan(config_dir: str) -> None:
    """Plan the changes"""
    try:
        with halo.Halo(text="Loading", spinner="dots") as spinner:
            spinner.text = "Loading config"
            config = gdbt.stencil.load.load_config(config_dir)

            spinner.text = "Loading resources"
            stencils = gdbt.stencil.load.load_resources(config_dir)

            spinner.text = "Resolving resources"
            resources = {}
            for key, value in stencils.items():
                stencil_resources = value.resolve(
                    key,
                    config.providers,
                    typing.cast(typing.Dict[str, typing.Any], config.evaluations),
                    typing.cast(typing.Dict[str, typing.Any], config.lookups),
                )
                resources.update(stencil_resources)
            state_desired = gdbt.state.state.State(resources)

            spinner.text = "Loading state"
            state_current = gdbt.state.state.load(
                config.state,
                typing.cast(
                    typing.Dict[str, gdbt.provider.provider.StateProvider], config.providers
                ),
            )

            spinner.text = "Calculating diff"
            state_diff = gdbt.state.diff.StateDiff(state_current, state_desired)

        changes = len(state_diff.outcomes(config.providers).values())
        if changes == 0:
            console.print("\n[b]Dashboards are up to date![/]\n")
            return

        console.print("\n[b]Planned changes:[/b]\n")
        console.print(state_diff.render(config.providers))
        console.print("\nRun [bold green]gdbt apply[/] to apply these changes\n")
    except gdbt.errors.Error as exc:
        console.print(f"[red][b]ERROR:[/b] {exc.message}")
        raise SystemExit(1)


@click.command()
@click.option(
    "-c",
    "--config-dir",
    type=click.STRING,
    default=".",
    help="Configuration directory",
)
@click.option(
    "-y",
    "--auto-approve",
    type=click.BOOL,
    default=False,
    is_flag=True,
    help="Do not ask for confirmation",
)
def apply(config_dir: str, auto_approve: bool) -> None:
    """Apply the changes"""
    try:
        with halo.Halo(text="Loading", spinner="dots") as spinner:
            spinner.text = "Loading config"
            config = gdbt.stencil.load.load_config(config_dir)

            spinner.text = "Loading resources"
            stencils = gdbt.stencil.load.load_resources(config_dir)

            spinner.text = "Resolving resources"
            resources = {}
            for key, value in stencils.items():
                stencil_resources = value.resolve(
                    key,
                    config.providers,
                    typing.cast(typing.Dict[str, typing.Any], config.evaluations),
                    typing.cast(typing.Dict[str, typing.Any], config.lookups),
                )
                resources.update(stencil_resources)
            state_desired = gdbt.state.state.State(resources)

            spinner.text = "Loading state"
            state_current = gdbt.state.state.load(
                config.state,
                typing.cast(
                    typing.Dict[str, gdbt.provider.provider.StateProvider], config.providers
                ),
            )

            spinner.text = "Calculating diff"
            state_diff = gdbt.state.diff.StateDiff(state_current, state_desired)

        changes = len(state_diff.outcomes(config.providers).values())
        if changes == 0:
            console.print("\n[b]Dashboards are up to date![/]\n")
            return

        console.print("\n[b]Pending changes:[/b]\n")
        console.print(state_diff.render(config.providers))
        console.print("\n")

        if not auto_approve:
            click.confirm("Apply?", abort=True)
            console.print("\n")

        t_start = time.time()
        plan = gdbt.state.plan.Plan(state_diff)
        state_applied = plan.apply(config.providers)
        t_end = time.time()
        duration = t_end - t_start

        with halo.Halo(text="Uploading state", spinner="dots") as spinner:
            gdbt.state.state.push(
                config.state,
                typing.cast(
                    typing.Dict[str, gdbt.provider.provider.StateProvider], config.providers
                ),
                state_applied,
            )
            spinner.succeed("Uploaded state")
        console.print(
            f"\n[bold green]Done! Modified {changes} resources in {duration:.2f} seconds."
        )
    except gdbt.errors.Error as exc:
        console.print(f"[red][b]ERROR:[/b] {exc.message}")
        raise SystemExit(1)


main.add_command(version)
main.add_command(plan)
main.add_command(apply)

if __name__ == "__main__":
    main()