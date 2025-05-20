DOCKER_IMAGE_NAME=$1

pull_docker_image()
{
    local i=
    local ok=false
    echo "Pulling the docker image if needed"

    if [ -z "${DOCKER_IMAGE_NAME}" ]; then
        echo "DOCKER_IMAGE_NAME not set, exiting..."
        exit
    fi
    for ((i=0; i<1; i++)); do
        docker pull "${DOCKER_IMAGE_NAME}" && ok=true && break
        echo "Docker pull failed, retrying..."
    done
    if ${ok}; then
        echo "Docker pull done"
    else
        echo "Docker pull failed for 3 times, aborting..."
        exit
    fi
    echo "Image has been prepared"
}

pull_docker_image