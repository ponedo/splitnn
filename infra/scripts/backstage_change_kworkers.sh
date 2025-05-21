#!/bin/bash

# Target scheduling policy and priority
TARGET_POLICY="SCHED_FIFO"
TARGET_PRIORITY=90

# Function to apply scheduling policy to kworker threads
update_ff_threads() {
    local pattern=$1
    ps -eLo pid,cls,comm | grep "${pattern}" | while read pid cls comm; do
        if [[ "$cls" != "FF" ]]; then
            echo "Updating kworker thread PID $pid ($comm) to $TARGET_POLICY with priority $TARGET_PRIORITY..."
            sudo chrt -f -p $TARGET_PRIORITY $pid
        fi
    done
}

# Main monitoring loop
update_ff_threads rcu
update_ff_threads ksoftirqd
while true; do
    update_ff_threads kworker
    sleep 1  # Check for new kworker threads every 5 seconds
done
