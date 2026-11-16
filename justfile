set shell := ["bash", "-euc"]

# List available commands
default:
    @just --list

# Build the production image locally
prod-build:
    docker build -t ghcr.io/kyxie/cloudcheckin:latest .

# Publish a patch release from a clean branch
release:
    bash scripts/release.sh patch

# Publish a minor release from a clean branch
minor:
    bash scripts/release.sh minor

# Publish a major release from a clean branch
major:
    bash scripts/release.sh major
