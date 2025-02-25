#!/usr/bin/env sh
#shellcheck shell=sh

set -x

REPO=gekowa
IMAGE=cue-splitter
PLATFORMS="linux/amd64"

docker context use x86_64
export DOCKER_CLI_EXPERIMENTAL="enabled"
# docker buildx use homecluster

# Build & push latest
docker buildx build --no-cache -t "${REPO}/${IMAGE}:latest" --compress --push --platform "${PLATFORMS}" .
