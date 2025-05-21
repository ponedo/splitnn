WORK_DIR=$(dirname $(readlink -f $0))

test_group_results_dir=$1
all_logs=$(find $test_group_results_dir -type f -name "link_log.txt")

for d in $all_logs; do
    ${WORK_DIR}/plot.sh $d
done