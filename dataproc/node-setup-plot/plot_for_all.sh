WORK_DIR=$(dirname $(readlink -f $0))

test_group_results_dir=$1
all_dirs=$(find $test_group_results_dir -type d -name "ctr_log")

for d in $all_dirs; do
    ${WORK_DIR}/plot.sh $d
done