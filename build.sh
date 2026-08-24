#!/bin/bash

# defaults
IMAGE_NAME=${IMAGE_NAME:-blacklanternsecurity/bbot-server}
TAG=${TAG:-latest}
PLATFORMS=${PLATFORMS:-linux/amd64,linux/arm64}
REGISTRY_TAG=${REGISTRY_TAG:-latest}

# store any custom build environment variables in the .env file...
# this allows you to build and store you own images, for whatever platforms you need, in whatever registry you want/need to...
test -f .env || {
    echo "Error: .env file not found"
    exit 1
}

source .env

docker buildx create --use --name multi-builder 
docker buildx build --platform "${PLATFORMS}" -t "${IMAGE_NAME}:${TAG}" --load .

# only try to push the image to the registry if $REGISTRY_IMAGE_NAME has been set...
if [ "${REGISTRY_IMAGE_NAME}x" != "x" ]; then
  docker tag "${IMAGE_NAME}:${TAG}" "${REGISTRY_IMAGE_NAME}:${REGISTRY_TAG}"
  docker push "${REGISTRY_IMAGE_NAME}:${REGISTRY_TAG}"
fi

# EOF
