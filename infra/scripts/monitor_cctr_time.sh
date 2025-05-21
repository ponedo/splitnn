#!/bin/bash
WORK_DIR=$(dirname $(readlink -f $0))/../
BPFTRACE_SCRIPT=${WORK_DIR}/scripts/monitor_cctr_time.bt

# Check arguments
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <output_file>"
    exit 1
fi

OUTPUT_FILE=$1

# Run the bpftrace script and redirect its output
mkdir -p $(dirname $OUTPUT_FILE)
trap 'kill -INT $BPFTRACE_PID' INT
trap 'kill -TERM $BPFTRACE_PID' TERM
bpftrace $BPFTRACE_SCRIPT > "$OUTPUT_FILE" &

BPFTRACE_PID=$!
wait $BPFTRACE_PID
