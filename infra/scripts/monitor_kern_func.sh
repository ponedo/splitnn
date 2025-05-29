#!/bin/bash

# Check arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <comm> <function> <output_file>"
    exit 1
fi

COMM=$1
FUNCTION=$2
OUTPUT_FILE=$3

# Generate an ad-hoc bpftrace script
BPFTRACE_SCRIPT=$(mktemp /tmp/monitor_XXXX.bt)

if [ -n "$COMM"  ]; then
    cat << EOF > $BPFTRACE_SCRIPT
#!/usr/bin/env bpftrace

kprobe:$FUNCTION
/comm == "$COMM"/
{
    @start[tid] = nsecs;
}

kretprobe:$FUNCTION
/@start[tid] && comm == "$COMM"/
{
    \$duration = nsecs - @start[tid];
    printf("%ld\n", \$duration);
    delete(@start[tid]);
}
EOF

else

    cat << EOF > $BPFTRACE_SCRIPT
#!/usr/bin/env bpftrace

kprobe:$FUNCTION
{
    @start[tid] = nsecs;
}

kretprobe:$FUNCTION
{
    \$duration = nsecs - @start[tid];
    printf("%ld\n", \$duration);
    delete(@start[tid]);
}
EOF

fi

# Run the bpftrace script and redirect its output
mkdir -p $(dirname $OUTPUT_FILE)
trap 'kill -INT $BPFTRACE_PID' INT
trap 'kill -TERM $BPFTRACE_PID' TERM
bpftrace $BPFTRACE_SCRIPT > "$OUTPUT_FILE" &

BPFTRACE_PID=$!
wait $BPFTRACE_PID

# Clean up
rm -f $BPFTRACE_SCRIPT
