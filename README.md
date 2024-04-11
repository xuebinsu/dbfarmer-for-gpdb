# DBFarmer for Greenplum 

DBFarmer can be used to create and manage database clusters in local containers. Currently it only supports Greenplum 7.1.0.

DBFarmer 能为您创建和管理运行在本地容器中的数据库集群。它目前仅支持 Greenplum 7.1.0 版本。

DBFarmer is an experimental project driven by curiosity. It is **not recommended** to use it in production.

DBFarmer 是一个由好奇心驱动的实验性项目，**不宜**用于生产环境。

If you have any comment, please do not hesitate to open an issue. Thank you!

如果您对本项目有任何意见，欢迎提 issue。谢谢！

Copyright (c) 2024 Xuebin Su (苏学斌)

## Prerequisites 使用前的准备

### Installing Python 3 安装 Python 3

Python 3.6 or above, and the venv module in the Python standard library, are required.

需要安装 Python 3.6 或以上版本，及 Python 标准库中的 venv 模块。

In some common Linux distributions (e.g. Debian 12), venv is provided separately in the `python3-venv` package.

在一些常见的 Linux 发行版（如 Debian 12）中，venv 模块是以 `python3-venv` 包单独提供的。

### Installing Container Engine 安装容器引擎

Docker Compose V2, or any compatible engine is required.

需要安装 Docker Compose V2 或任何与之兼容的容器引擎。

Please make sure `docker` is in the environment variable `PATH`.

请确认 `docker` 在环境变量 `PATH` 包含的路径中。

### (Optional) Installing Greenplum Server （可选）安装 Greenplum 服务器

In some cases, you might want to run the cluster as native processes instead of in containers.

在某些情况下，您可能想让集群以本地进程的方式运行，而非运行在容器中。

Then, you will need to install the Greenplum server (version 7.1.0 is required).

此时，您需要安装 Greenplum 服务器程序（要求 7.1.0 版本）。

After installation, please `source` the `greenplum-path.sh` script in the installation directory.

在安装完成后，请 `source` 安装目录下的 `greenplum-path.sh` 脚本。


## Using DBFarmer's Utilities 使用 DBFarmer 的工具程序

Cloning this repo to localhost completes the installation of DBFarmer.

将本代码仓库克隆至本地即完成了 DBFarmer 的安装。

You can enjoy all of DBFarmer by just running its utilities.

您可以通过运行 DBFarmer 的工具程序使用 DBFarmer 的所有功能。

In the utilities, `compose.py` is used to define and manage database clusters in local containers. You might want to check its usage with

```
~/dbfarmer$ python3 compose.py --help
usage: compose.py [-h] [--dry-run] {up,down,build} ...

Define and manage database clusters in local containers

options:
  -h, --help       show this help message and exit
  --dry-run

subcommands:
  {up,down,build}
    up             create and start a database cluster
    down           stop and remove a database cluster
    build          build container image for database clusters
```

其中，`compose.py` 用于在容器中定义和管理数据库集群，您可以通过如下方式查看其用法：

```
~/dbfarmer$ DBFARMER_LANG=zh_CN python3 compose.py --help
usage: compose.py [-h] [--dry-run] {up,down,build} ...

定义和管理运行在您本地容器中的数据库集群

options:
  -h, --help       show this help message and exit
  --dry-run

subcommands:
  {up,down,build}
    up             创建并启动一个数据库集群
    down           停止并删除一个数据库集群
    build          为数据库集群创建容器镜像
```

And if you want to check the usage of a subcommand, e.g. `up`, just run

```
~/dbfarmer$ python3 compose.py up --help
usage: compose.py up [-h] [--port PORT] [--num-segments NUM_SEGMENTS]

create and start a database cluster

options:
  -h, --help            show this help message and exit
  --port PORT           port to connect to the cluster, also used as the coordinator's port (default: 12345)
  --num-segments NUM_SEGMENTS
                        number of segments in the cluster, using ports from (PORT + 1) to (PORT + NUM_SEGMENTS) (default: 1)
```

要查看其中某个子命令（如 `up`）的用法，您可以运行

```
~/dbfarmer$ DBFARMER_LANG=zh_CN python3 compose.py up --help
usage: compose.py up [-h] [--port PORT] [--num-segments NUM_SEGMENTS]

创建并启动一个数据库集群

options:
  -h, --help            show this help message and exit
  --port PORT           用于连接集群的端口号，同时也用作协调节点（coordinator）的监听端口号 (default: 12345)
  --num-segments NUM_SEGMENTS
                        集群中数据节点（segment）的数量，会使用从 (PORT + 1) 到 (PORT + NUM_SEGMENTS) 号端口 (default: 1)
```

For running clusters with native processes, you might want to use the `local.py` utility. Its usage is similar to `compose.py`.

当您要以本地进程运行集群时，您可以运行 `local.py` 工具程序。其用法与 `compose.py` 类似。
