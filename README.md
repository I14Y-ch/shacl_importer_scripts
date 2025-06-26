# shacl_importer_scripts

A collection of scripts for importing data structures and transforming them to SHACL (Shapes Constraint Language).

## Features

- Import data structures from various sources
- Create SHACL shapes corresponding to those structures

Available converters: 
- CSV importer
- DSD importer (to recover the old structures of I14Y)
- Import template to build structure from scratch
    - Excel template
    - Json template
- Postgres importer
- XSD importer

## Requirements

- Python 3.8+
- `rdflib`
- `pyshacl`

## Installation

There is no installation required. Each script can be run separately to generate a SHACL file as needed from each source.

## Contributing

Contributions are welcome! Please open issues or submit pull requests.
