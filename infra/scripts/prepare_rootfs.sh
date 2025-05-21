DOCKER_IMAGE_NAME=$1

WORK_DIR=$(dirname $(readlink -f $0))/../
TMP_DIR="${WORK_DIR}/tmp"
IMAGE_ARCHIVES_DIR="${TMP_DIR}/img_archives"
IMAGE_LAYERS_DIR="${TMP_DIR}/img_layers"
IMAGE_BUNDLES_DIR="${TMP_DIR}/img_bundles"
IMAGE_ROOTFS_DIR=


get_docker_created_ts()
{
    local img_name=$1
    local ts_orig_str=$(docker inspect ${img_name} --format '{{.Created}}')
    ts_str="${ts_orig_str//[^0-9]/}"
    if [ -n "${ts_str}" ]; then
        echo "${ts_str}"
    else
        echo "NOT_CREATED"
    fi
}


get_local_img_created_ts()
{
    local img_layer_dir=$1
    local img_tag=$2
    local ts_orig_str=$(skopeo inspect oci:${img_layer_dir}:${img_tag} --format '{{.Created}}')
    ts_mid_str="$(echo ${ts_orig_str} | awk '{print $1$2}')"
    ts_str="${ts_mid_str//[^0-9]/}"
    if [ -n "${ts_str}" ]; then
        echo "${ts_str}"
    else
        echo "NOT_CREATED"
    fi
}


check_local_docker_image()
{
    IFS=":" read -r DOCKER_IMAGE_REPO DOCKER_IMAGE_TAG <<< "${DOCKER_IMAGE_NAME}"
    local res="NOT_FOUND"
    entries=$(docker images | grep "${DOCKER_IMAGE_REPO}")
    while IFS= read -r line <<< $entries; do
        tag=$(echo "$line" | awk '{print $2}')
        if [ "${tag}" = "${DOCKER_IMAGE_TAG}" ]; then
            res="FOUND"
            break
        fi
    done
    if [ "${res}" = "FOUND" ]; then
        echo "FOUND"
    else
        echo "NOT_FOUND"
    fi
}


pull_docker_image()
{
    local i=
    local ok=false
    echo "Pulling the docker image if needed"

    if [ -z "${DOCKER_IMAGE_NAME}" ]; then
        echo "DOCKER_IMAGE_NAME not set, exiting..."
        exit
    fi
    local local_exist=$(check_local_docker_image)
    # echo "local_exist $local_exist"
    # if [ "${local_exist}" = "FOUND" ]; then
    #     echo "Image found in local images"
    # else
        for ((i=0; i<3; i++)); do
            docker pull "${DOCKER_IMAGE_NAME}" && ok=true && break
            echo "Docker pull failed, retrying..."
        done
        if ${ok}; then
            echo "Docker pull done"
        else
            echo "Docker pull failed for 3 times, aborting..."
            exit
        fi
    # fi
    echo "Image has been prepared"
}


setup_rootfs()
{
    # Extract the rootfs of the docker image
    IFS=":" read -r DOCKER_IMAGE_REPO DOCKER_IMAGE_TAG <<< "${DOCKER_IMAGE_NAME}"
    if [ -z "${DOCKER_IMAGE_TAG}" ]; then
        DOCKER_IMAGE_TAG="latest"
    fi
    IMAGE_ARCHIVE_DIR=${IMAGE_ARCHIVES_DIR}/${DOCKER_IMAGE_REPO}
    IMAGE_LAYER_DIR="${IMAGE_LAYERS_DIR}/${DOCKER_IMAGE_REPO}"
    IMAGE_OVERLAYFS_DIR="${IMAGE_BUNDLES_DIR}/${DOCKER_IMAGE_REPO}/${DOCKER_IMAGE_TAG}"
    IMAGE_ROOTFS_DIR="${IMAGE_OVERLAYFS_DIR}/rootfs"

    local docker_created_ts=$(get_docker_created_ts ${DOCKER_IMAGE_NAME})
    local local_img_created_ts=$(get_local_img_created_ts ${IMAGE_LAYER_DIR} ${DOCKER_IMAGE_TAG})
    if [ "${docker_created_ts}" != "NOT_CREATED" ] && \
        [ "${local_img_created_ts}" != "NOT_CREATED" ] && \
        [ "${docker_created_ts}" = "${local_img_created_ts}" ]; then
        # Target rootfs has been prepared before, use the cache
        echo "Rootfs cache of ${DOCKER_IMAGE_NAME} is available"
        echo "Image rootfs is stored at: ${IMAGE_ROOTFS_DIR}"
    else
        # Target rootfs is not prepared, extract the rootfs
        echo "Rootfs cache of ${DOCKER_IMAGE_NAME} is unavailable, extracting rootfs..."
        mkdir -p ${IMAGE_ARCHIVE_DIR} ${IMAGE_LAYER_DIR} ${IMAGE_OVERLAYFS_DIR}
        docker save "${DOCKER_IMAGE_NAME}" -o "${IMAGE_ARCHIVE_DIR}/${DOCKER_IMAGE_TAG}.tar"
        skopeo copy \
            "docker-archive://${IMAGE_ARCHIVE_DIR}/${DOCKER_IMAGE_TAG}.tar" \
            "oci:${IMAGE_LAYER_DIR}:${DOCKER_IMAGE_TAG}"
        rm -rf "${IMAGE_OVERLAYFS_DIR}"
        umoci unpack --image "${IMAGE_LAYER_DIR}:${DOCKER_IMAGE_TAG}" "${IMAGE_OVERLAYFS_DIR}"
        if [ ! -d "${IMAGE_ROOTFS_DIR}" ]; then
            echo "Image rootfs creation failed! Exiting..."
            exit
        else
            echo "Image rootfs is stored at: ${IMAGE_ROOTFS_DIR}"
        fi
    fi
}

# Main
setup_rootfs