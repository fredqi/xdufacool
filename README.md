# xdufacool: XDU-Faculty Toolkit

![Unit Tests](https://github.com/fredqi/xdufacool/workflows/Unit%20Tests/badge.svg)

----

A set of toolkit for faculty members in the Xidian University.

## Installation

To create an environment for development, you can use the following command:

```bash
conda create -n xdufacool-dev python=3.12 pandoc
conda activate xdufacool-dev
```

To install the package, you can use the following command:

```bash
pip install -e .
```

## Usage

The `xdufacool` toolkit provides two main subcommands: `create` and `collect`.

### `create` subcommand

The `create` subcommand is used to create assignment packages for distribution.

**Usage:**

```bash
xdufacool create [-h] [-c CONFIG] [-o OUTPUT_DIR] [assignment_ids ...]
```

**Arguments:**

*   `-h`, `--help`: Show help message and exit.
*   `-c`, `--config`: Path to the configuration file (default: `config.yml`).
*   `-o`, `--output-dir`: Output directory for the assignment packages (default: `dist`).
*   `assignment_ids`: (Optional) List of assignment IDs to create. If not specified, all assignments in the config file will be created.

**Example:**

To create all assignments specified in the `config.yml` file and save them to the `dist` directory:

```bash
xdufacool create
```

To create only the assignments with IDs `hw01` and `hw02`:

```bash
xdufacool create -c config.yml -o assignments hw01 hw02
```

### `collect` subcommand

The `collect` subcommand is used to collect student submissions.

**Usage:**

```bash
xdufacool collect [-h] [-c CONFIG] submission_dir [assignment_ids ...]
```

**Arguments:**

*   `-h`, `--help`: Show help message and exit.
*   `-c`, `--config`: Path to the configuration file (default: `config.yml`).
*   `submission_dir`: The directory containing student submissions.
*   `assignment_ids`: (Optional) List of assignment IDs to collect. If not specified, submissions for all assignments in the config file will be collected.

**Example:**

To collect submissions for all assignments from the `submissions` directory:

```bash
xdufacool collect submissions
```

To collect submissions only for the assignment with ID `hw01`:

```bash
xdufacool collect -c config.yml submissions hw01
```

## Configuration

The `xdufacool` toolkit is configured using a YAML file (default: `config.yml`). The configuration file specifies the course details, assignments, and other settings. Refer to the example `config.yml` file for more details on the configuration format.
