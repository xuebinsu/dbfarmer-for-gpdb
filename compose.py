from argparse import Namespace
from subprocess import run, STDOUT, Popen
from getpass import getuser

from local import run_cmd, TOP_DIR, WORK_DIR, define_and_parse_args, health_check


def prepare_src_tar(gpdb_version: str):
    gpdb_src_filename = f"gpdb_src-{gpdb_version}.tar.gz"
    if not (WORK_DIR / gpdb_src_filename).is_file():
        run_cmd(
            [
                "curl",
                f"https://codeload.github.com/greenplum-db/gpdb/tar.gz/refs/tags/{gpdb_version}",
                "--output",
                WORK_DIR / gpdb_src_filename,
            ]
        )
    run_cmd(["make", "-C", TOP_DIR / "src", "install"])
    dbfarmer_src_filename = "dbfarmer_src.tar.gz"
    run_cmd(
        ["tar", "-czvf", WORK_DIR / dbfarmer_src_filename, "-C", TOP_DIR / "src", "."]
    )


CONTAINER_IMAGE_NAME = "dbfarmer:gpdb"


def build_image(args: Namespace):
    assert (
        args.server_version == "7.1.0"
    ), f"Greenplum {args.server_version} is not supported."
    prepare_src_tar(args.server_version)
    run_cmd(
        [
            "docker",
            "build",
            "--build-arg",
            f"user={getuser()}",
            "--build-arg",
            f"server_version={args.server_version}",
            "--tag",
            CONTAINER_IMAGE_NAME,
            "--file",
            WORK_DIR / "dockerfile",
            WORK_DIR,
        ]
    )


def make_compose_config(port: int, num_segments: int):
    def service_name(contentid):
        return "coordinator" if contentid == -1 else f"primary-{contentid}"

    def volume_name(contentid):
        return f"pgdata-{service_name(contentid)}"

    coordinator_config = {
        "environment": [
            "CLUSTER_DBID=1",
            "CLUSTER_CONTENTID=-1",
            f"CLUSTER_NUM_SEGMENTS={num_segments}",
            f"PGPORT={port}",
            f"CLUSTER_COORDINATOR_HOST={service_name(-1)}",
        ],
        "image": CONTAINER_IMAGE_NAME,
        "volumes": [f"{volume_name(-1)}:/home/{getuser()}/pgdata"],
        "networks": ["default"],
        "ports": [f"{port}:{port}"],
    }

    def segment_config(contentid):
        return {
            "environment": [
                f"CLUSTER_DBID={contentid + 2}",
                f"CLUSTER_CONTENTID={contentid}",
                f"PGPORT={port + contentid + 1}",
                f"CLUSTER_COORDINATOR_HOST={service_name(-1)}",
                f"CLUSTER_COORDINATOR_PORT={port}",
            ],
            "image": CONTAINER_IMAGE_NAME,
            "volumes": [f"{volume_name(contentid)}:/home/{getuser()}/pgdata"],
            "networks": ["default"],
        }

    return {
        "version": "3",
        "name": "dbfarmer-for-gpdb",
        "networks": {"default": None},
        "volumes": {
            volume_name(contentid): None for contentid in range(-1, num_segments)
        },
        "services": {
            service_name(contentid): (
                coordinator_config if contentid == -1 else segment_config(contentid)
            )
            for contentid in range(-1, num_segments)
        },
    }


def venv_make_compose_file(port: int, num_segments: int) -> str:
    from yaml import dump

    try:
        from yaml import CDumper as Dumper
    except ImportError:
        from yaml import Dumper

    with open(WORK_DIR / "compose.yaml", "w") as compose_file:
        dump(
            make_compose_config(port, num_segments),
            compose_file,
            Dumper=Dumper,
            default_flow_style=False,
        )

    print("OK_MAKE_COMPOSE_FILE")


def make_compose_file(port: int, num_segments: int):
    run_cmd(["python3", "-m", "venv", TOP_DIR / ".venv"])

    from shlex import quote

    python_cmd = (
        f"from compose import venv_make_compose_file; "
        f"venv_make_compose_file({port}, {num_segments})"
    )
    bash_cmd = (
        f"source {TOP_DIR / '.venv' / 'bin' / 'activate'} && "
        f"pip3 install PyYAML && "
        f"python3 -c {quote(python_cmd)} | grep OK_MAKE_COMPOSE_FILE"
    )
    print(f"Running {repr(bash_cmd)}")
    p = run(
        bash_cmd,
        stderr=STDOUT,
        check=True,
        shell=True,
        text=True,
        cwd=TOP_DIR,
        executable="/bin/bash",
    )
    return p


def down(args):
    cmd = ["docker", "compose", "-f", WORK_DIR / "compose.yaml", "down"]
    if args.remove_data:
        cmd.append("--volumes")
    run_cmd(cmd)


def up(args: Namespace):
    print(make_compose_file(args.port, args.num_segments))
    p = Popen(["docker", "compose", "-f", WORK_DIR / "compose.yaml", "up"], text=True)
    print(p)
    health_check(args.port)


if __name__ == "__main__":
    args = define_and_parse_args(
        "Define and manage database clusters in local containers",
        "定义和管理运行在您本地容器中的数据库集群",
        subcommands={"up": up, "down": down, "build": build_image},
    )
