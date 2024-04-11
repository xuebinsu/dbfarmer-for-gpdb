import sys

assert sys.version_info >= (3, 6), f"Python version >= 3.6 is required."

from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from subprocess import CompletedProcess, CalledProcessError, STDOUT, run, Popen, PIPE
from pathlib import Path
import os
from socket import gethostname
from time import sleep
from typing import Any, Callable, List, Dict, Optional


def run_cmd(
    cmd: List[str],
    retry_interval: int = -1,
    capture_output: bool = False,
    dry_run: bool = False,
) -> Optional[CompletedProcess]:
    while True:
        try:
            if dry_run:
                print(f"Running {cmd}")
                return None
            return run(
                cmd,
                universal_newlines=True,
                stdout=PIPE if capture_output else None,
                stderr=STDOUT,
                check=True,
            )
        except CalledProcessError as e:
            if retry_interval < 0:
                raise Exception(e.output) from e
            else:
                sleep(retry_interval)


TOP_DIR = Path(
    run_cmd(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.strip()
)
WORK_DIR = TOP_DIR / "container"
LOCAL_DATA_DIR = TOP_DIR / "pgdata"


def start_server(contentid: int, env: Dict[str, str]):
    merged_env = os.environ.copy()
    for k, v in env.items():
        merged_env[k] = v
    merged_env["CLUSTER_CONTENTID"] = f"{contentid}"
    merged_env["PGDATA"] = LOCAL_DATA_DIR / f"primary_{contentid}"
    merged_env["CLUSTER_COORDINATOR_HOST"] = gethostname()
    log_dir = LOCAL_DATA_DIR / "log"
    run_cmd(["mkdir", "-p", log_dir])
    f = open(log_dir / f"startup_{contentid}.log", "w")
    p = Popen(
        ["bash", WORK_DIR / "entrypoint.sh"],
        universal_newlines=True,
        stdout=f,
        stderr=f,
        env=merged_env,
    )
    return p, f


def start_cluster(port: int, num_segments: int):
    return [
        start_server(
            contentid,
            {
                "CLUSTER_DBID": f"{contentid + 2}",
                "PGPORT": f"{port + contentid + 1}",
                "CLUSTER_NUM_SEGMENTS": f"{num_segments}",
                "CLUSTER_COORDINATOR_PORT": f"{port}",
            },
        )
        for contentid in range(-1, num_segments)
    ]


def install_extension():
    run_cmd(["make", "-C", TOP_DIR / "src", "install"])


def health_check(port: int):
    sql = (
        "SELECT gp_segment_id FROM gp_id "
        "UNION ALL "
        "SELECT gp_segment_id FROM gp_dist_random('gp_id');"
    )
    run_cmd(
        [
            "psql",
            "postgres",
            "-h",
            gethostname(),
            "-p",
            f"{port}",
            "-c",
            sql,
        ],
        retry_interval=1,
    )


def define_and_parse_args(
    description: str,
    chinese_description: str,
    subcommands: Dict[str, Callable[[Namespace], Any]],
):
    help_in_chinese = (
        "DBFARMER_LANG" in os.environ
        and os.environ["DBFARMER_LANG"].split(".")[0] == "zh_CN"
    )
    parser = ArgumentParser(
        description=chinese_description if help_in_chinese else description,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", default=False)
    helps = (
        {
            "up": "创建并启动一个数据库集群",
            "down": "停止并删除一个数据库集群",
            "build": "为数据库集群创建容器镜像",
            "--port": "用于连接集群的端口号，同时也用作协调节点（coordinator）的监听端口号",
            "--num-segments": "集群中数据节点（segment）的数量，会使用从 (PORT + 1) 到 (PORT + NUM_SEGMENTS) 号端口",
            "--remove-data": "在删除集群的同时删除其中的所有数据（危险！）",
            "--server-version": "数据库服务器程序的版本",
        }
        if help_in_chinese
        else {
            "up": "create and start a database cluster",
            "down": "stop and remove a database cluster",
            "build": "build container image for database clusters",
            "--port": "port to connect to the cluster, also used as the coordinator's port",
            "--num-segments": "number of segments in the cluster, using ports from (PORT + 1) to (PORT + NUM_SEGMENTS)",
            "--remove-data": "remove all data when removing the cluster (dangerous!)",
            "--server-version": "version of the database server program",
        }
    )
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")
    parser_up = subparsers.add_parser(
        "up",
        description=helps["up"],
        help=helps["up"],
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser_up.add_argument("--port", type=int, help=helps["--port"], default=12345)
    parser_up.add_argument(
        "--num-segments", type=int, help=helps["--num-segments"], default=1
    )
    parser_down = subparsers.add_parser(
        "down",
        description=helps["down"],
        help=helps["down"],
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser_down.add_argument(
        "--remove-data", action="store_true", help=helps["--remove-data"]
    )
    if "build" in subcommands:
        parser_build = subparsers.add_parser(
            "build",
            description=helps["build"],
            help=helps["build"],
            formatter_class=ArgumentDefaultsHelpFormatter,
        )
        parser_build.add_argument(
            "--server-version", help=helps["--server-version"], default="7.1.0"
        )

    args = parser.parse_args(args=None if len(sys.argv) > 1 else ["--help"])
    assert args.subcommand is not None, "Subcommand is missing"

    return args


def up(args: Namespace):
    install_extension()
    servers = start_cluster(args.port, args.num_segments)
    print(servers)
    health_check(args.port)


def down(args: Namespace):
    for d in LOCAL_DATA_DIR.iterdir():
        postmaster_file_path = d / "postmaster.pid"
        if d.is_dir() and postmaster_file_path.exists():
            with open(postmaster_file_path) as lock_file:
                run_cmd(["kill", lock_file.readline().strip()])
    if args.remove_data:
        run_cmd(["rm", "-rf", LOCAL_DATA_DIR])
        print(f"Data directory '{LOCAL_DATA_DIR}' removed")


if __name__ == "__main__":
    subcommands = {"up": up, "down": down}
    args = define_and_parse_args(
        "Define and manage database clusters on your localhost",
        "定义和管理运行在您本机上的数据库集群",
        subcommands,
    )
    assert not args.dry_run, "Dry run is not supported yet"
    subcommands[args.subcommand](args)
